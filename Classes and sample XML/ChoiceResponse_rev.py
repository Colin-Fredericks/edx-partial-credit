#-----------------------------------------------------------------------------
@registry.register
class ChoiceResponse(LoncapaResponse):
    """
    This response type is used when the student chooses from a discrete set of
    choices. Currently, to be marked correct, all "correct" choices must be
    supplied by the student, and no extraneous choices may be included.

    This response type allows for two inputtypes: radiogroups and checkbox
    groups. radiogroups are used when the student should select a single answer,
    and checkbox groups are used when the student may supply 0+ answers.
    Note: it is suggested to include a "None of the above" choice when no
    answer is correct for a checkboxgroup inputtype; this ensures that a student
    must actively mark something to get credit.

    If two choices are marked as correct with a radiogroup, the student will
    have no way to get the answer right.

    TODO: Allow for marking choices as 'optional' and 'required', which would
    not penalize a student for including optional answers and would also allow
    for questions in which the student can supply one out of a set of correct
    answers.This would also allow for survey-style questions in which all
    answers are correct.

    Example:

    <choiceresponse>
        <radiogroup>
            <choice correct="false">
                <text>This is a wrong answer.</text>
            </choice>
            <choice correct="true">
                <text>This is the right answer.</text>
            </choice>
            <choice correct="false">
                <text>This is another wrong answer.</text>
            </choice>
        </radiogroup>
    </choiceresponse>

    In the above example, radiogroup can be replaced with checkboxgroup to allow
    the student to select more than one choice.

    TODO: In order for the inputtypes to render properly, this response type
    must run setup_response prior to the input type rendering. Specifically, the
    choices must be given names. This behavior seems like a leaky abstraction,
    and it'd be nice to change this at some point.

    """

    human_name = _('Checkboxes')
    tags = ['choiceresponse']
    max_inputfields = 1
    allowed_inputfields = ['checkboxgroup', 'radiogroup']
    correct_choices = None
    has_responsive_ui = True

    def setup_response(self):

        self.assign_choice_names()

        correct_xml = self.xml.xpath(
            '//*[@id=$id]//choice[@correct="true"]',
            id=self.xml.get('id')
        )

        self.correct_choices = set([choice.get(
            'name') for choice in correct_xml])

        incorrect_xml = self.xml.xpath(
            '//*[@id=$id]//choice[@correct="false"]',
            id=self.xml.get('id')
        )

        self.incorrect_choices = set([choice.get(
            'name') for choice in incorrect_xml])

    def assign_choice_names(self):
        """
        Initialize name attributes in <choice> tags for this response.
        """

        for index, choice in enumerate(self.xml.xpath('//*[@id=$id]//choice',
                                                      id=self.xml.get('id'))):
            choice.set("name", "choice_" + str(index))

    def grade_via_edc(self, all_choices, student_answer, student_non_answers):
        """
        Calculates partial credit on the EDC scheme.
        For each correctly selected or correctly blank choice, score 1 point.
        Divide by total number of choices.
        Returns a CorrectMap.
        """

        edc_max_grade = len(all_choices)
        edc_current_grade = 0

        good_answers = sum([1 for answer in student_answer if answer in self.correct_choices])
        good_non_answers = sum([1 for blank in student_non_answers if blank in self.incorrect_choices])
        edc_current_grade = good_answers + good_non_answers

        return_grade = round(self.get_max_score() * float(edc_current_grade) / float(edc_max_grade), 2)

        if edc_current_grade > 0:
            return CorrectMap(self.answer_id, correctness='partially-correct', npoints=return_grade)
        else:
            return CorrectMap(self.answer_id, correctness='incorrect', npoints=0)

    def grade_via_halves(self, all_choices, student_answer, student_non_answers):
        """
        Calculates partial credit on the Halves scheme.
        If no errors, full credit.
        If one error, half credit as long as there are 3+ choices
        If two errors, 1/4 credit as long as there are 5+ choices
        (If not enough choices, no credit.)
        Returns a CorrectMap
        """

        halves_error_count = 0

        incorrect_answers = sum([1 for answer in student_answer if answer in self.incorrect_choices])
        missed_answers = sum([1 for blank in student_non_answers if blank in self.correct_choices])
        halves_error_count = incorrect_answers + missed_answers

        if halves_error_count == 0:
            return_grade = self.get_max_score()
            return CorrectMap(self.answer_id, correctness='correct', npoints=return_grade)
        elif halves_error_count == 1 and len(all_choices) > 2:
            return_grade = round(self.get_max_score() / 2.0, 2)
            return CorrectMap(self.answer_id, correctness='partially-correct', npoints=return_grade)
        elif halves_error_count == 2 and len(all_choices) > 4:
            return_grade = round(self.get_max_score() / 4.0, 2)
            return CorrectMap(self.answer_id, correctness='partially-correct', npoints=return_grade)
        else:
            return CorrectMap(self.answer_id, 'incorrect')

    def get_score(self, student_answers):

        # Setting up answer lists:
        #  all_choices: the full list of checkboxes
        #  student_answer: what the student actually chose (note no "s")
        #  student_non_answer: what they didn't choose
        #  self.correct_choices: boxes that should be checked
        #  self.incorrect_choices: boxes that should NOT be checked

        all_choices = self.correct_choices.union(self.incorrect_choices)

        student_answer = student_answers.get(self.answer_id, [])

        if not isinstance(student_answer, list):
            student_answer = [student_answer]

        # "None apply" should really be a valid choice for "check all that apply",
        # but it throws an error if all the checks are blank.
        no_empty_answer = student_answer != []

        student_answer = set(student_answer)

        student_non_answers = all_choices - student_answer

        if not no_empty_answer:
            return CorrectMap(self.answer_id, 'incorrect')

        # This below checks to see whether we're using an alternate grading scheme.
        #  Set partial_credit="false" (or remove it) to require an exact answer for any credit.
        #  Set partial_credit="EDC" to count each choice for equal points (Every Decision Counts).
        #  Set partial_credit="halves" to take half credit off for each error.

        tree = self.xml
        problem_xml = tree.xpath('.')

        # Partial credit type - only one type at a time right now.
        credit_type = problem_xml[0].get('partial_credit', default=False)

        try:
            credit_type = str(credit_type).lower().strip()
        except ValueError:
            _ = self.capa_system.i18n.ugettext
            # Translators: 'partial_credit' is an attribute name and should not be translated.
            # 'EDC' and 'halves' and 'false' should also not be translated.
            msg = _("partial_credit value should be one of 'EDC', 'halves', or 'false'.")
            raise LoncapaProblemError(msg)

        if credit_type == 'false':
            pass
        elif credit_type == 'halves':
            return self.grade_via_halves(all_choices, student_answer, student_non_answers)
        elif credit_type == 'edc':
            return self.grade_via_edc(all_choices, student_answer, student_non_answers)

        required_selected = len(self.correct_choices - student_answer) == 0
        no_extra_selected = len(student_answer - self.correct_choices) == 0

        correct = required_selected & no_extra_selected & no_empty_answer

        if correct:
            return CorrectMap(self.answer_id, 'correct')
        else:
            return CorrectMap(self.answer_id, 'incorrect')

    def get_answers(self):
        return {self.answer_id: list(self.correct_choices)}

#-----------------------------------------------------------------------------
