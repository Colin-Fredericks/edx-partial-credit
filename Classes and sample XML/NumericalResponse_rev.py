#-----------------------------------------------------------------------------


@registry.register
class NumericalResponse(LoncapaResponse):
    """
    This response type expects a number or formulaic expression that evaluates
    to a number (e.g. `4+5/2^2`), and accepts with a tolerance.
    """

    human_name = _('Numerical Input')
    tags = ['numericalresponse']
    hint_tag = 'numericalhint'
    allowed_inputfields = ['textline', 'formulaequationinput']
    required_attributes = ['answer']
    max_inputfields = 1
    has_responsive_ui = True

    def __init__(self, *args, **kwargs):
        self.correct_answer = ''
        self.tolerance = default_tolerance
        self.range_tolerance = False
        self.answer_range = self.inclusion = None
        super(NumericalResponse, self).__init__(*args, **kwargs)

    def setup_response(self):
        xml = self.xml
        context = self.context
        answer = xml.get('answer')

        if answer.startswith(('[', '(')) and answer.endswith((']', ')')):  # range tolerance case
            self.range_tolerance = True
            self.inclusion = (
                True if answer.startswith('[') else False, True if answer.endswith(']') else False
            )
            try:
                self.answer_range = [contextualize_text(x, context) for x in answer[1:-1].split(',')]
                self.correct_answer = answer[0] + self.answer_range[0] + ', ' + self.answer_range[1] + answer[-1]
            except Exception:
                log.debug("Content error--answer '%s' is not a valid range tolerance answer", answer)
                _ = self.capa_system.i18n.ugettext
                raise StudentInputError(
                    _("There was a problem with the staff answer to this problem.")
                )
        else:
            self.correct_answer = contextualize_text(answer, context)

            # Find the tolerance
            tolerance_xml = xml.xpath(
                '//*[@id=$id]//responseparam[@type="tolerance"]/@default',
                id=xml.get('id')
            )
            if tolerance_xml:  # If it isn't an empty list...
                self.tolerance = contextualize_text(tolerance_xml[0], context)

    def get_staff_ans(self, answer):
        """
        Given the staff answer as a string, find its float value.

        Use `evaluator` for this, but for backward compatability, try the
        built-in method `complex` (which used to be the standard).
        """
        try:
            correct_ans = complex(answer)
        except ValueError:
            # When `correct_answer` is not of the form X+Yj, it raises a
            # `ValueError`. Then test if instead it is a math expression.
            # `complex` seems to only generate `ValueErrors`, only catch these.
            try:
                correct_ans = evaluator({}, {}, answer)
            except Exception:
                log.debug("Content error--answer '%s' is not a valid number", answer)
                _ = self.capa_system.i18n.ugettext
                raise StudentInputError(
                    _("There was a problem with the staff answer to this problem.")
                )

        return correct_ans

    def get_score(self, student_answers):
        """
        Grade a numeric response.
        """
        student_answer = student_answers[self.answer_id]

        _ = self.capa_system.i18n.ugettext
        general_exception = StudentInputError(
            _(u"Could not interpret '{student_answer}' as a number.").format(student_answer=cgi.escape(student_answer))
        )

        # Begin `evaluator` block
        # Catch a bunch of exceptions and give nicer messages to the student.
        try:
            student_float = evaluator({}, {}, student_answer)
        except UndefinedVariable as undef_var:
            raise StudentInputError(
                _(u"You may not use variables ({bad_variables}) in numerical problems.").format(bad_variables=undef_var.message)
            )
        except ValueError as val_err:
            if 'factorial' in val_err.message:
                # This is thrown when fact() or factorial() is used in an answer
                #   that evaluates on negative and/or non-integer inputs
                # ve.message will be: `factorial() only accepts integral values` or
                # `factorial() not defined for negative values`
                raise StudentInputError(
                    _("factorial function evaluated outside its domain:"
                      "'{student_answer}'").format(student_answer=cgi.escape(student_answer))
                )
            else:
                raise general_exception
        except ParseException:
            raise StudentInputError(
                _(u"Invalid math syntax: '{student_answer}'").format(student_answer=cgi.escape(student_answer))
            )
        except Exception:
            raise general_exception
        # End `evaluator` block -- we figured out the student's answer!


        tree = self.xml
        problem_xml = tree.xpath('.')
        
        # Partial credit type - can set 'close' or 'list'
        credit_type = problem_xml[0].get('partial_credit', default=False)
        
        # Allowing for multiple partial credit types. Divide on commas, strip whitespace.
        if credit_type:
            credit_type = credit_type.split(',')
            credit_type = [word.strip().lower() for word in credit_type]
        
        # What multiple of the tolerance is worth partial credit?
        has_partial_range = tree.xpath('responseparam[@partial-range]')
        if has_partial_range:
            partial_range = has_partial_range[0].get('partial-range', default='2')
            partial_range = float(re.sub('\D', '', partial_range)) # Keep only digits in case people want to write 'x2' or '2x'
        else:
            partial_range = 2
        
        # Take in alternative answers that are worth partial credit.
        has_partial_answers = tree.xpath('responseparam[@partial_answers]')
        if has_partial_answers:
            partial_answers = has_partial_answers[0].get('partial_answers').split(',')
            for index, word in enumerate(partial_answers):
                partial_answers[index] = word.strip()
                partial_answers[index] = self.get_staff_ans(partial_answers[index])

        else:
            partial_answers = False
        
        partial_score = 0.5
        
        cmap = CorrectMap(self.answer_id)
        is_correct = 'incorrect'

        if self.range_tolerance:
            if isinstance(student_float, complex):
                raise StudentInputError(_(u"You may not use complex numbers in range tolerance problems"))
            boundaries = []
            for inclusion, answer in zip(self.inclusion, self.answer_range):
                boundary = self.get_staff_ans(answer)
                if boundary.imag != 0:
                    # Translators: This is an error message for a math problem. If the instructor provided a boundary
                    # (end limit) for a variable that is a complex number (a + bi), this message displays.
                    raise StudentInputError(_("There was a problem with the staff answer to this problem: complex boundary."))
                if isnan(boundary):
                    # Translators: This is an error message for a math problem. If the instructor did not provide
                    # a boundary (end limit) for a variable, this message displays.
                    raise StudentInputError(_("There was a problem with the staff answer to this problem: empty boundary."))
                boundaries.append(boundary.real)
                if compare_with_tolerance(
                        student_float,
                        boundary,
                        tolerance=float_info.epsilon,
                        relative_tolerance=True
                ):
                    is_correct = inclusion
                    break
            else:
                if boundaries[0] < student_float < boundaries[1]:
                    is_correct = 'correct'
                else:
                    if credit_type is False:
                        pass
                    elif 'close' in credit_type:
                        """
                        Partial credit: 50% if the student is outside the specified boundaries,
                        but within an extended set of boundaries.
                        """
                        extended_boundaries = []
                        boundary_range = boundaries[1]-boundaries[0]
                        extended_boundaries.append(boundaries[0] - partial_range * boundary_range)
                        extended_boundaries.append(boundaries[1] + partial_range * boundary_range)
                        if extended_boundaries[0] < student_float < extended_boundaries[1]:
                            is_correct = 'partially-correct'
                    
        else:
            correct_float = self.get_staff_ans(self.correct_answer)
            
            """
            Partial credit is available in three cases:
            - If the student answer is within expanded tolerance of the actual answer,
              the student gets 50% credit. (Currently set as the default.)
              Set via partial_credit="close" in the numericalresponse tag.
              
            - If the student answer is within regular tolerance of an alternative answer, 
              the student gets 50% credit. (Same default.)
              Set via partial_credit="list"
              
            - If the student answer is within expanded tolerance of an alternative answer,
              the student gets 25%. (We take the 50% and square it, at the moment.)
              Set via partial_credit="list,close" or "close, list" or the like.
            """
            
            if str(self.tolerance).endswith('%'):
                expanded_tolerance = str(partial_range * float(str(self.tolerance)[:-1])) + '%'
            else:
                expanded_tolerance = partial_range * float(self.tolerance)
            
            if compare_with_tolerance(student_float, correct_float, self.tolerance):
                is_correct = 'correct'
            elif credit_type is False:
                pass
            elif 'list' in credit_type:
                for value in partial_answers:
                    if compare_with_tolerance(student_float, value, self.tolerance):
                        is_correct = 'partially-correct'
                    elif 'close' in credit_type:
                        if compare_with_tolerance(student_float, value, self.tolerance):
                            is_correct = 'partially-correct'
                            partial_score = partial_score * partial_score
            elif 'close' in credit_type:
                if compare_with_tolerance(student_float, correct_float, expanded_tolerance):
                    is_correct = 'partially-correct'
        
        if is_correct == 'partially-correct':
            return CorrectMap(self.answer_id, correctness=is_correct, npoints=partial_score)
        else:
            return CorrectMap(self.answer_id, correctness=is_correct)
        

    def compare_answer(self, ans1, ans2):
        """
        Outside-facing function that lets us compare two numerical answers,
        with this problem's tolerance.
        """
        return compare_with_tolerance(
            evaluator({}, {}, ans1),
            evaluator({}, {}, ans2),
            self.tolerance
        )

    def validate_answer(self, answer):
        """
        Returns whether this answer is in a valid form.
        """
        try:
            evaluator(dict(), dict(), answer)
            return True
        except (StudentInputError, UndefinedVariable):
            return False

    def get_answers(self):
        return {self.answer_id: self.correct_answer}

#-----------------------------------------------------------------------------
