#-----------------------------------------------------------------------------


@registry.register
class MultipleChoiceResponse(LoncapaResponse):
    """
    Multiple Choice Response
    The shuffle and answer-pool features on this class enable permuting and
    subsetting the choices shown to the student.
    Both features enable name "masking":
    With masking, the regular names of multiplechoice choices
    choice_0 choice_1 ... are not used. Instead we use random masked names
    mask_2 mask_0 ... so that a view-source of the names reveals nothing about
    the original order. We introduce the masked names right at init time, so the
    whole software stack works with just the one system of naming.
    The .has_mask() test on a response checks for masking, implemented by a
    ._has_mask attribute on the response object.
    The logging functionality in capa_base calls the unmask functions here
    to translate back to choice_0 name style for recording in the logs, so
    the logging is in terms of the regular names.
    """
    # TODO: handle direction and randomize

    human_name = _('Multiple Choice')
    tags = ['multiplechoiceresponse']
    max_inputfields = 1
    allowed_inputfields = ['choicegroup']
    correct_choices = None

    def setup_response(self):
        # call secondary setup for MultipleChoice questions, to set name
        # attributes
        self.mc_setup_response()

        # define correct choices (after calling secondary setup)
        xml = self.xml
        cxml = xml.xpath('//*[@id=$id]//choice', id=xml.get('id'))

        # contextualize correct attribute and then select ones for which
        # correct = "true", with separate list for those with partial credit point values.
        self.correct_choices = [
            contextualize_text(choice.get('name'), self.context)
            for choice in cxml
            if contextualize_text(choice.get('correct'), self.context) == 'true'
        ]
        self.partial_choices = [
            contextualize_text(choice.get('name'), self.context)
            for choice in cxml
            if contextualize_text(choice.get('correct'), self.context) == 'partial'
        ]
        self.partial_values = [
            float(choice.get('point_value', default='0.5'))    # Default partial credit: 50%
            for choice in cxml
            if contextualize_text(choice.get('correct'), self.context) == 'partial'
        ]

    def mc_setup_response(self):
        """
        Initialize name attributes in <choice> stanzas in the <choicegroup> in this response.
        Masks the choice names if applicable.
        """
        i = 0
        for response in self.xml.xpath("choicegroup"):
            # Is Masking enabled? -- check for shuffle or answer-pool features
            ans_str = response.get("answer-pool")
            # Masking (self._has_mask) is off, to be re-enabled with a future PR.
            rtype = response.get('type')
            if rtype not in ["MultipleChoice"]:
                # force choicegroup to be MultipleChoice if not valid
                response.set("type", "MultipleChoice")
            for choice in list(response):
                # The regular, non-masked name:
                if choice.get("name") is not None:
                    name = "choice_" + choice.get("name")
                else:
                    name = "choice_" + str(i)
                    i += 1
                # If using the masked name, e.g. mask_0, save the regular name
                # to support unmasking later (for the logs).
                if self.has_mask():
                    mask_name = "mask_" + str(mask_ids.pop())
                    self._mask_dict[mask_name] = name
                    choice.set("name", mask_name)
                else:
                    choice.set("name", name)

    def late_transforms(self, problem):
        """
        Rearrangements run late in the __init__ process.
        Cannot do these at response init time, as not enough
        other stuff exists at that time.
        """
        self.do_shuffle(self.xml, problem)
        self.do_answer_pool(self.xml, problem)

    def get_score(self, student_answers):
        """
        grade student response.
        """
        # log.debug('%s: student_answers=%s, correct_choices=%s' % (
        #   unicode(self), student_answers, self.correct_choices))
        
        tree = self.xml
        partialcredit = tree.xpath('choicegroup[@partial_credit]')
        credit_type = False
        if partialcredit:
            credit_type = partialcredit[0].get('partial_credit')

            try:
                credit_type = str(credit_type).lower().strip()
            except ValueError:
                _ = self.capa_system.i18n.ugettext
                # Translators: 'partial_credit' is an attribute name and should not be translated.
                msg = _("partial_credit value can only be set to 'points' or removed.")
                raise LoncapaProblemError(msg)
        
        if (self.answer_id in student_answers
                and student_answers[self.answer_id] in self.correct_choices):
            return CorrectMap(self.answer_id, correctness='correct')
        elif credit_type == 'points' and (self.answer_id in student_answers
                and student_answers[self.answer_id] in self.partial_choices):
            choice_index = self.partial_choices.index(student_answers[self.answer_id])
            credit_amount = self.partial_values[choice_index]
            return CorrectMap(self.answer_id, correctness='partially-correct', npoints=credit_amount)
        else:
            return CorrectMap(self.answer_id, 'incorrect')

    def get_answers(self):
        return {self.answer_id: self.correct_choices}

    def unmask_name(self, name):
        """
        Given a masked name, e.g. mask_2, returns the regular name, e.g. choice_0.
        Fails with LoncapaProblemError if called on a response that is not masking.
        """
        if not self.has_mask():
            _ = self.capa_system.i18n.ugettext
            # Translators: 'unmask_name' is a method name and should not be translated.
            msg = _("unmask_name called on response that is not masked")
            raise LoncapaProblemError(msg)
        return self._mask_dict[name]

    def unmask_order(self):
        """
        Returns a list of the choice names in the order displayed to the user,
        using the regular (non-masked) names.
        """
        # With masking disabled, this computation remains interesting to see
        # the displayed order, even though there is no unmasking.
        choices = self.xml.xpath('choicegroup/choice')
        return [choice.get("name") for choice in choices]

    def do_shuffle(self, tree, problem):
        """
        For a choicegroup with shuffle="true", shuffles the choices in-place in the given tree
        based on the seed. Otherwise does nothing.
        Raises LoncapaProblemError if both shuffle and answer-pool are active:
        a problem should use one or the other but not both.
        Does nothing if the tree has already been processed.
        """
        # The tree is already pared down to this <multichoiceresponse> so this query just
        # gets the child choicegroup (i.e. no leading //)
        choicegroups = tree.xpath('choicegroup[@shuffle="true"]')
        if choicegroups:
            choicegroup = choicegroups[0]
            if choicegroup.get('answer-pool') is not None:
                _ = self.capa_system.i18n.ugettext
                # Translators: 'shuffle' and 'answer-pool' are attribute names and should not be translated.
                msg = _("Do not use shuffle and answer-pool at the same time")
                raise LoncapaProblemError(msg)
            # Note in the response that shuffling is done.
            # Both to avoid double-processing, and to feed the logs.
            if self.has_shuffle():
                return
            self._has_shuffle = True  # pylint: disable=attribute-defined-outside-init
            # Move elements from tree to list for shuffling, then put them back.
            ordering = list(choicegroup.getchildren())
            for choice in ordering:
                choicegroup.remove(choice)
            ordering = self.shuffle_choices(ordering, self.get_rng(problem))
            for choice in ordering:
                choicegroup.append(choice)

    def shuffle_choices(self, choices, rng):
        """
        Returns a list of choice nodes with the shuffling done,
        using the provided random number generator.
        Choices with 'fixed'='true' are held back from the shuffle.
        """
        # Separate out a list of the stuff to be shuffled
        # vs. the head/tail of fixed==true choices to be held back from the shuffle.
        # Rare corner case: A fixed==true choice "island" in the middle is lumped in
        # with the tail group of fixed choices.
        # Slightly tricky one-pass implementation using a state machine
        head = []
        middle = []  # only this one gets shuffled
        tail = []
        at_head = True
        for choice in choices:
            if at_head and choice.get('fixed') == 'true':
                head.append(choice)
                continue
            at_head = False
            if choice.get('fixed') == 'true':
                tail.append(choice)
            else:
                middle.append(choice)
        rng.shuffle(middle)
        return head + middle + tail

    def get_rng(self, problem):
        """
        Get the random number generator to be shared by responses
        of the problem, creating it on the problem if needed.
        """
        # Multiple questions in a problem share one random number generator (rng) object
        # stored on the problem. If each question got its own rng, the structure of multiple
        # questions within a problem could appear predictable to the student,
        # e.g. (c) keeps being the correct choice. This is due to the seed being
        # defined at the problem level, so the multiple rng's would be seeded the same.
        # The name _shared_rng begins with an _ to suggest that it is not a facility
        # for general use.
        # pylint: disable=protected-access
        if not hasattr(problem, '_shared_rng'):
            problem._shared_rng = random.Random(self.context['seed'])
        return problem._shared_rng

    def do_answer_pool(self, tree, problem):
        """
        Implements the answer-pool subsetting operation in-place on the tree.
        Allows for problem questions with a pool of answers, from which answer options shown to the student
        and randomly selected so that there is always 1 correct answer and n-1 incorrect answers,
        where the author specifies n as the value of the attribute "answer-pool" within <choicegroup>

        The <choicegroup> tag must have an attribute 'answer-pool' giving the desired
        pool size. If that attribute is zero or not present, no operation is performed.
        Calling this a second time does nothing.
        Raises LoncapaProblemError if the answer-pool value is not an integer,
        or if the number of correct or incorrect choices available is zero.
        """
        choicegroups = tree.xpath("choicegroup[@answer-pool]")
        if choicegroups:
            choicegroup = choicegroups[0]
            num_str = choicegroup.get('answer-pool')
            if num_str == '0':
                return
            try:
                num_choices = int(num_str)
            except ValueError:
                _ = self.capa_system.i18n.ugettext
                # Translators: 'answer-pool' is an attribute name and should not be translated.
                msg = _("answer-pool value should be an integer")
                raise LoncapaProblemError(msg)

            # Note in the response that answerpool is done.
            # Both to avoid double-processing, and to feed the logs.
            if self.has_answerpool():
                return
            self._has_answerpool = True  # pylint: disable=attribute-defined-outside-init

            choices_list = list(choicegroup.getchildren())

            # Remove all choices in the choices_list (we will add some back in later)
            for choice in choices_list:
                choicegroup.remove(choice)

            rng = self.get_rng(problem)  # random number generator to use
            # Sample from the answer pool to get the subset choices and solution id
            (solution_id, subset_choices) = self.sample_from_answer_pool(choices_list, rng, num_choices)

            # Add back in randomly selected choices
            for choice in subset_choices:
                choicegroup.append(choice)

            # Filter out solutions that don't correspond to the correct answer we selected to show
            # Note that this means that if the user simply provides a <solution> tag, nothing is filtered
            solutionset = choicegroup.xpath('../following-sibling::solutionset')
            if len(solutionset) != 0:
                solutionset = solutionset[0]
                solutions = solutionset.xpath('./solution')
                for solution in solutions:
                    if solution.get('explanation-id') != solution_id:
                        solutionset.remove(solution)

    def sample_from_answer_pool(self, choices, rng, num_pool):
        """
        Takes in:
            1. list of choices
            2. random number generator
            3. the requested size "answer-pool" number, in effect a max

        Returns a tuple with 2 items:
            1. the solution_id corresponding with the chosen correct answer
            2. (subset) list of choice nodes with num-1 incorrect and 1 correct

        Raises an error if the number of correct or incorrect choices is 0.
        """

        correct_choices = []
        incorrect_choices = []

        for choice in choices:
            if choice.get('correct') == 'true':
                correct_choices.append(choice)
            else:
                incorrect_choices.append(choice)
                # In my small test, capa seems to treat the absence of any correct=
                # attribute as equivalent to ="false", so that's what we do here.

        # We raise an error if the problem is highly ill-formed.
        # There must be at least one correct and one incorrect choice.
        # IDEA: perhaps this sort semantic-lint constraint should be generalized to all multichoice
        # not just down in this corner when answer-pool is used.
        # Or perhaps in the overall author workflow, these errors are unhelpful and
        # should all be removed.
        if len(correct_choices) < 1 or len(incorrect_choices) < 1:
            _ = self.capa_system.i18n.ugettext
            # Translators: 'Choicegroup' is an input type and should not be translated.
            msg = _("Choicegroup must include at least 1 correct and 1 incorrect choice")
            raise LoncapaProblemError(msg)

        # Limit the number of incorrect choices to what we actually have
        num_incorrect = num_pool - 1
        num_incorrect = min(num_incorrect, len(incorrect_choices))

        # Select the one correct choice
        index = rng.randint(0, len(correct_choices) - 1)
        correct_choice = correct_choices[index]
        solution_id = correct_choice.get('explanation-id')

        # Put together the result, pushing most of the work onto rng.shuffle()
        subset_choices = [correct_choice]
        rng.shuffle(incorrect_choices)
        subset_choices += incorrect_choices[:num_incorrect]
        rng.shuffle(subset_choices)

        return (solution_id, subset_choices)


@registry.register
class TrueFalseResponse(MultipleChoiceResponse):

    human_name = _('True/False Choice')
    tags = ['truefalseresponse']

    def mc_setup_response(self):
        i = 0
        for response in self.xml.xpath("choicegroup"):
            response.set("type", "TrueFalse")
            for choice in list(response):
                if choice.get("name") is None:
                    choice.set("name", "choice_" + str(i))
                    i += 1
                else:
                    choice.set("name", "choice_" + choice.get("name"))

    def get_score(self, student_answers):
        correct = set(self.correct_choices)
        answers = set(student_answers.get(self.answer_id, []))

        if correct == answers:
            return CorrectMap(self.answer_id, 'correct')

        return CorrectMap(self.answer_id, 'incorrect')

#-----------------------------------------------------------------------------