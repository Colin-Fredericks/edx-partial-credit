#-----------------------------------------------------------------------------


@registry.register
class OptionResponse(LoncapaResponse):
    """
    TODO: handle direction and randomize
    """

    human_name = _('Dropdown')
    tags = ['optionresponse']
    hint_tag = 'optionhint'
    allowed_inputfields = ['optioninput']
    answer_fields = None
    has_responsive_ui = True

    def setup_response(self):
        self.answer_fields = self.inputfields

    def get_score(self, student_answers):
        # log.debug('%s: student_answers=%s' % (unicode(self),student_answers))
        cmap = CorrectMap()

        amap = self.get_answers()

        tree = self.xml
        problem_xml = tree.xpath('.')

        # Partial credit type - can set 'points' only at the moment.
        credit_type = problem_xml[0].get('partial_credit', default=False)

        try:
            credit_type = str(credit_type).lower().strip()
        except ValueError:
            _ = self.capa_system.i18n.ugettext
            # Translators: 'partial_credit' is an attribute name and should not be translated.
            msg = _("partial_credit value can only be set to 'points' or be removed.")
            raise LoncapaProblemError(msg)

        for aid in amap:
            for word in amap[aid]:
                if aid in student_answers and student_answers[aid] == word:
                    cmap.set(aid, 'correct')
                    break
                else:
                    cmap.set(aid, 'incorrect')

            # For partial credit:
            if credit_type == 'points':
                partial_map = self.get_partial()
                points_map = self.get_partial_points(partial_map)

                if not cmap.is_correct(aid) and partial_map[aid] is not None:
                    for index, word in enumerate(partial_map[aid]):
                        if aid in student_answers and student_answers[aid] == word:
                            cmap.set(aid, 'partially-correct')
                            cmap.set_property(aid, 'npoints', points_map[aid][index])
                            break
                        else:
                            cmap.set(aid, 'incorrect')

            answer_variable = self.get_student_answer_variable_name(student_answers, aid)
            if answer_variable:
                cmap.set_property(aid, 'answervariable', answer_variable)

        return cmap

    def get_answers(self):
        amap = dict([(af.get('id'), contextualize_text(af.get(
            'correct'), self.context)) for af in self.answer_fields])
        # Split to allow multiple correct answers.
        for aid in amap:
            amap[aid] = amap[aid].split(',')
            for index, word in enumerate(amap[aid]):
                amap[aid][index] = word.strip()
        # log.debug('%s: expected answers=%s' % (unicode(self),amap))
        return amap

    def get_partial(self):
        """
        Returns a dictionary similar to the answer map,
        but with all the partially-correct answers instead.
        """
        pmap = dict([(af.get('id'), contextualize_text(af.get(
            'partial'), self.context)) for af in self.answer_fields])
        # Split to allow multiple partially correct answers.
        for aid in pmap:
            if pmap[aid] is not None:
                pmap[aid] = pmap[aid].split(',')
                for index, word in enumerate(pmap[aid]):
                    pmap[aid][index] = word.strip()
        # log.debug('%s: partially correct answers=%s' % (unicode(self),amap))
        return pmap

    def get_partial_points(self, partial_map):
        """
        This dictionary matches the one returned by get_partial,
        but gives the point value for the responses instead.
        """

        default_credit = 0.5

        pointsmap = dict([(af.get('id'), contextualize_text(af.get(
            'point_values', default=None), self.context)) for af in self.answer_fields])

        for aid in pointsmap:
            if pointsmap[aid] is not None:
                pointsmap[aid] = pointsmap[aid].split(',')
                for index, word in enumerate(pointsmap[aid]):
                    pointsmap[aid][index] = float(word.strip())
            else:
                pointsmap[aid] = [default_credit] * len(partial_map[aid])
        # log.debug('%s: partial point values=%s' % (unicode(self),amap))
        return pointsmap

    def get_student_answer_variable_name(self, student_answers, aid):
        """
        Return student answers variable name if exist in context else None.
        """
        if aid in student_answers:
            for key, val in self.context.iteritems():
                # convert val into unicode because student answer always be a unicode string
                # even it is a list, dict etc.
                if unicode(val) == student_answers[aid]:
                    return '$' + key
        return None

#-----------------------------------------------------------------------------
