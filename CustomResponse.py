#-----------------------------------------------------------------------------


@registry.register
class CustomResponse(LoncapaResponse):
    """
    Custom response.  The python code to be run should be in <answer>...</answer>
    or in a <script>...</script>
    """

    human_name = _('Custom Evaluated Script')
    tags = ['customresponse']

    allowed_inputfields = ['textline', 'textbox', 'crystallography',
                           'chemicalequationinput', 'vsepr_input',
                           'drag_and_drop_input', 'editamoleculeinput',
                           'designprotein2dinput', 'editageneinput',
                           'annotationinput', 'jsinput', 'formulaequationinput']
    code = None
    expect = None
    
    # Standard amount for partial credit if not otherwise specified:
    default_pc = 0.5

    def setup_response(self):
        xml = self.xml

        # if <customresponse> has an "expect" (or "answer") attribute then save
        # that
        self.expect = xml.get('expect') or xml.get('answer')

        log.debug('answer_ids=%s', self.answer_ids)

        # the <answer>...</answer> stanza should be local to the current <customresponse>.
        # So try looking there first.
        self.code = None
        answer = None
        try:
            answer = xml.xpath('//*[@id=$id]//answer', id=xml.get('id'))[0]
        except IndexError:
            # print "xml = ",etree.tostring(xml,pretty_print=True)

            # if we have a "cfn" attribute then look for the function specified by cfn, in
            # the problem context ie the comparison function is defined in the
            # <script>...</script> stanza instead
            cfn = xml.get('cfn')
            if cfn:
                log.debug("cfn = %s", cfn)

                # This is a bit twisty.  We used to grab the cfn function from
                # the context, but now that we sandbox Python execution, we
                # can't get functions from previous executions.  So we make an
                # actual function that will re-execute the original script,
                # and invoke the function with the data needed.
                def make_check_function(script_code, cfn):
                    def check_function(expect, ans, **kwargs):
                        extra_args = "".join(", {0}={0}".format(k) for k in kwargs)
                        code = (
                            script_code + "\n" +
                            "cfn_return = %s(expect, ans%s)\n" % (cfn, extra_args)
                        )
                        globals_dict = {
                            'expect': expect,
                            'ans': ans,
                        }
                        globals_dict.update(kwargs)
                        safe_exec.safe_exec(
                            code,
                            globals_dict,
                            python_path=self.context['python_path'],
                            extra_files=self.context['extra_files'],
                            slug=self.id,
                            random_seed=self.context['seed'],
                            unsafely=self.capa_system.can_execute_unsafe_code(),
                        )
                        return globals_dict['cfn_return']
                    return check_function

                self.code = make_check_function(self.context['script_code'], cfn)

        if not self.code:
            if answer is None:
                log.error("[courseware.capa.responsetypes.customresponse] missing"
                          " code checking script! id=%s", self.id)
                self.code = ''
            else:
                answer_src = answer.get('src')
                if answer_src is not None:
                    # TODO: this code seems not to be used any more since self.capa_system.filesystem doesn't exist.
                    self.code = self.capa_system.filesystem.open('src/' + answer_src).read()
                else:
                    self.code = answer.text

    def get_score(self, student_answers):
        """
        student_answers is a dict with everything from request.POST, but with the first part
        of each key removed (the string before the first "_").
        """
        _ = self.capa_system.i18n.ugettext

        log.debug('%s: student_answers=%s', unicode(self), student_answers)

        # ordered list of answer id's
        # sort the responses on the bases of the problem's position number
        # which can be found in the last place in the problem id. Then convert
        # this number into an int, so that we sort on ints instead of strings
        idset = sorted(self.answer_ids, key=lambda x: int(x.split("_")[-1]))
        try:
            # ordered list of answers
            submission = [student_answers[k] for k in idset]
        except Exception as err:
            msg = u"[courseware.capa.responsetypes.customresponse] {message}\n idset = {idset}, error = {err}".format(
                message=_("error getting student answer from {student_answers}").format(student_answers=student_answers),
                idset=idset,
                err=err
            )

            log.error(
                "[courseware.capa.responsetypes.customresponse] error getting"
                " student answer from %s"
                "\n idset = %s, error = %s",
                student_answers, idset, err
            )
            raise Exception(msg)

        # global variable in context which holds the Presentation MathML from dynamic math input
        # ordered list of dynamath responses
        dynamath = [student_answers.get(k + '_dynamath', None) for k in idset]

        # if there is only one box, and it's empty, then don't evaluate
        if len(idset) == 1 and not submission[0]:
            # default to no error message on empty answer (to be consistent with other
            # responsetypes) but allow author to still have the old behavior by setting
            # empty_answer_err attribute
            msg = (u'<span class="inline-error">{0}</span>'.format(_(u'No answer entered!'))
                   if self.xml.get('empty_answer_err') else '')
            return CorrectMap(idset[0], 'incorrect', msg=msg)

        # NOTE: correct = 'unknown' could be dangerous. Inputtypes such as textline are
        # not expecting 'unknown's
        correct = ['unknown'] * len(idset)
        messages = [''] * len(idset)
        overall_message = ""

        # put these in the context of the check function evaluator
        # note that this doesn't help the "cfn" version - only the exec version
        self.context.update({
            # my ID
            'response_id': self.id,

            # expected answer (if given as attribute)
            'expect': self.expect,

            # ordered list of student answers from entry boxes in our subtree
            'submission': submission,

            # ordered list of ID's of all entry boxes in our subtree
            'idset': idset,

            # ordered list of all javascript inputs in our subtree
            'dynamath': dynamath,

            # dict of student's responses, with keys being entry box IDs
            'answers': student_answers,

            # the list to be filled in by the check function
            'correct': correct,

            # the list of messages to be filled in by the check function
            'messages': messages,

            # a message that applies to the entire response
            # instead of a particular input
            'overall_message': overall_message,

            # any options to be passed to the cfn
            'options': self.xml.get('options'),
            'testdat': 'hello world',
        })

        # Pass DEBUG to the check function.
        self.context['debug'] = self.capa_system.DEBUG

        # Run the check function
        self.execute_check_function(idset, submission)

        # build map giving "correct"ness of the answer(s)
        correct = self.context['correct']
        messages = self.context['messages']
        overall_message = self.clean_message_html(self.context['overall_message'])
        grade_decimals = self.context.get('grade_decimals')

        correct_map = CorrectMap()
        correct_map.set_overall_message(overall_message)

        for k in range(len(idset)):
            max_points = self.maxpoints[idset[k]]
            if grade_decimals:
                npoints = max_points * grade_decimals[k]
            else:
                npoints = max_points if correct[k] == 'correct' else 0
                npoints = max_points * default_pc if correct[k] == 'partially-correct' else 0
            correct_map.set(idset[k], correct[k], msg=messages[k],
                            npoints=npoints)
        return correct_map

    def execute_check_function(self, idset, submission):
        # exec the check function
        if isinstance(self.code, basestring):
            try:
                safe_exec.safe_exec(
                    self.code,
                    self.context,
                    cache=self.capa_system.cache,
                    python_path=self.context['python_path'],
                    extra_files=self.context['extra_files'],
                    slug=self.id,
                    random_seed=self.context['seed'],
                    unsafely=self.capa_system.can_execute_unsafe_code(),
                )
            except Exception as err:
                self._handle_exec_exception(err)

        else:
            # self.code is not a string; it's a function we created earlier.

            # this is an interface to the Tutor2 check functions
            fn = self.code
            answer_given = submission[0] if (len(idset) == 1) else submission
            kwnames = self.xml.get("cfn_extra_args", "").split()
            kwargs = {n: self.context.get(n) for n in kwnames}
            log.debug(" submission = %s", submission)
            try:
                ret = fn(self.expect, answer_given, **kwargs)
            except Exception as err:  # pylint: disable=broad-except
                self._handle_exec_exception(err)
            log.debug(
                "[courseware.capa.responsetypes.customresponse.get_score] ret = %s",
                ret
            )
            if isinstance(ret, dict):
                # One kind of dictionary the check function can return has the
                # form {'ok': BOOLEAN or STRING, 'msg': STRING, 'grade_decimal' (optional): FLOAT (between 0.0 and 1.0)}
                # 'ok' will control the checkmark, while grade_decimal, if present, will scale
                # the score the student receives on the response.
                # If there are multiple inputs, they all get marked
                # to the same correct/incorrect value
                if 'ok' in ret:
                    """
                    Returning any falsy value for "ok" gives incorrect.
                    Returning any string that includes "partial" for "ok" gives partial credit.
                    Returning any other truthy value for "ok" gives correct
                    """
                    if ret['ok'] == False:
                        correct = 'incorrect'
                    elif 'partial' in str(ret['ok']):
                        correct = 'partially-correct'
                    else:
                        correct = 'correct'
                    correct = [correct] * len(idset)
                    # old version, no partial credit:
                    # correct = ['correct' if ret['ok'] else 'incorrect'] * len(idset)
                    msg = ret.get('msg', None)
                    msg = self.clean_message_html(msg)

                    # If there is only one input, apply the message to that input
                    # Otherwise, apply the message to the whole problem
                    if len(idset) > 1:
                        self.context['overall_message'] = msg
                    else:
                        self.context['messages'][0] = msg

                    if 'grade_decimal' in ret:
                        decimal = ret['grade_decimal']
                    else:
                        decimal = 1.0 if ret['ok'] else 0.0
                        decimal = default_pc if 'partial' in str(ret['ok']) else 0.0
                    grade_decimals = [decimal] * len(idset)
                    self.context['grade_decimals'] = grade_decimals

                # Another kind of dictionary the check function can return has
                # the form:
                # { 'overall_message': STRING,
                #   'input_list': [
                #     { 'ok': BOOLEAN or STRING, 'msg': STRING, 'grade_decimal' (optional): FLOAT (between 0.0 and 1.0)},
                #   ...
                #   ]
                # }
                # 'ok' will control the checkmark, while grade_decimal, if present, will scale
                # the score the student receives on the response.
                #
                # This allows the function to return an 'overall message'
                # that applies to the entire problem, as well as correct/incorrect
                # status, scaled grades, and messages for individual inputs
                elif 'input_list' in ret:
                    overall_message = ret.get('overall_message', '')
                    input_list = ret['input_list']

                    correct = []
                    messages = []
                    grade_decimals = []
                    """
                    Returning any falsy value for "ok" gives incorrect.
                    Returning any string that includes "partial" for "ok" gives partial credit.
                    Returning any other truthy value for "ok" gives correct
                    """
                    for input_dict in input_list:
                        if input_dict['ok'] == False:
                            correct.append('incorrect')
                        elif 'partial' in str(input_dict['ok']):
                            correct.append('partially-correct')
                        else:
                            correct.append('correct')
                            
                        # old version, no partial credit 
                        # correct.append('correct'
                        #                if input_dict['ok'] else 'incorrect')
                        
                        msg = (self.clean_message_html(input_dict['msg'])
                               if 'msg' in input_dict else None)
                        messages.append(msg)
                        if 'grade_decimal' in input_dict:
                            decimal = input_dict['grade_decimal']
                        else:
                            decimal = 1.0 if input_dict['ok'] else 0.0
                            decimal = default_pc if 'partial' in str(input_dict['ok']) else 0.0
                        grade_decimals.append(decimal)

                    self.context['messages'] = messages
                    self.context['overall_message'] = overall_message
                    self.context['grade_decimals'] = grade_decimals

                # Otherwise, we do not recognize the dictionary
                # Raise an exception
                else:
                    log.error(traceback.format_exc())
                    _ = self.capa_system.i18n.ugettext
                    raise ResponseError(
                        _("CustomResponse: check function returned an invalid dictionary!")
                    )

            else:
                """
                Returning any falsy value for "ok" gives incorrect.
                Returning any string that includes "partial" for "ok" gives partial credit.
                Returning any other truthy value for "ok" gives correct
                """
                
                if ret == False:
                    correct ='incorrect'
                elif 'partial' in str(ret):
                    correct = 'partially-correct'
                else:
                    correct = 'correct'
                correct = [correct] * len(idset)

                # old version, no partial credit:
                # correct = ['correct' if ret else 'incorrect'] * len(idset)

            self.context['correct'] = correct

    def clean_message_html(self, msg):

        # If *msg* is an empty string, then the code below
        # will return "</html>".  To avoid this, we first check
        # that *msg* is a non-empty string.
        if msg:

            # When we parse *msg* using etree, there needs to be a root
            # element, so we wrap the *msg* text in <html> tags
            msg = '<html>' + msg + '</html>'

            # Replace < characters
            msg = msg.replace('&#60;', '&lt;')

            # Use etree to prettify the HTML
            msg = etree.tostring(fromstring_bs(msg, convertEntities=None),
                                 pretty_print=True)

            msg = msg.replace('&#13;', '')

            # Remove the <html> tags we introduced earlier, so we're
            # left with just the prettified message markup
            msg = re.sub('(?ms)<html>(.*)</html>', '\\1', msg)

            # Strip leading and trailing whitespace
            return msg.strip()

        # If we start with an empty string, then return an empty string
        else:
            return ""

    def get_answers(self):
        """
        Give correct answer expected for this response.

        use default_answer_map from entry elements (eg textline),
        when this response has multiple entry objects.

        but for simplicity, if an "expect" attribute was given by the content author
        ie <customresponse expect="foo" ...> then that.
        """
        if len(self.answer_ids) > 1:
            return self.default_answer_map
        if self.expect:
            return {self.answer_ids[0]: self.expect}
        return self.default_answer_map

    def _handle_exec_exception(self, err):
        """
        Handle an exception raised during the execution of
        custom Python code.

        Raises a ResponseError
        """

        # Log the error if we are debugging
        msg = 'Error occurred while evaluating CustomResponse'
        log.warning(msg, exc_info=True)

        # Notify student with a student input error
        _, _, traceback_obj = sys.exc_info()
        raise ResponseError(err.message, traceback_obj)

#-----------------------------------------------------------------------------
