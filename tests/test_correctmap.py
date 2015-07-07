"""
Tests to verify that CorrectMap behaves correctly
"""

import unittest
from capa.correctmap import CorrectMap
import datetime


class CorrectMapTest(unittest.TestCase):
    """
    Tests to verify that CorrectMap behaves correctly
    """

    def setUp(self):
        super(CorrectMapTest, self).setUp()
        self.cmap = CorrectMap()

    def test_set_input_properties(self):
        # Set the correctmap properties for three inputs
        self.cmap.set(
            answer_id='1_2_1',
            correctness='correct',
            npoints=5,
            msg='Test message',
            hint='Test hint',
            hintmode='always',
            queuestate={
                'key': 'secretstring',
                'time': '20130228100026'
            }
        )

        self.cmap.set(
            answer_id='2_2_1',
            correctness='incorrect',
            npoints=None,
            msg=None,
            hint=None,
            hintmode=None,
            queuestate=None
        )

        self.cmap.set(
            answer_id='3_2_1',
            correctness='partially-correct',
            npoints=3,
            msg=None,
            hint=None,
            hintmode=None,
            queuestate=None
        )

        # Assert that each input has the expected properties
        self.assertTrue(self.cmap.is_correct('1_2_1'))
        self.assertFalse(self.cmap.is_correct('2_2_1'))
        self.assertTrue(self.cmap.is_correct('3_2_1'))

        self.assertTrue(self.cmap.is_partially_correct('3_2_1'))
        self.assertFalse(self.cmap.is_partially_correct('2_2_1'))

        self.assertEqual(self.cmap.get_correctness('1_2_1'), 'correct')
        self.assertEqual(self.cmap.get_correctness('2_2_1'), 'incorrect')
        self.assertEqual(self.cmap.get_correctness('3_2_1'), 'partially-correct')

        self.assertEqual(self.cmap.get_npoints('1_2_1'), 5)
        self.assertEqual(self.cmap.get_npoints('2_2_1'), 0)
        self.assertEqual(self.cmap.get_npoints('3_2_1'), 3)

        self.assertEqual(self.cmap.get_msg('1_2_1'), 'Test message')
        self.assertEqual(self.cmap.get_msg('2_2_1'), None)

        self.assertEqual(self.cmap.get_hint('1_2_1'), 'Test hint')
        self.assertEqual(self.cmap.get_hint('2_2_1'), None)

        self.assertEqual(self.cmap.get_hintmode('1_2_1'), 'always')
        self.assertEqual(self.cmap.get_hintmode('2_2_1'), None)

        self.assertTrue(self.cmap.is_queued('1_2_1'))
        self.assertFalse(self.cmap.is_queued('2_2_1'))

        self.assertEqual(self.cmap.get_queuetime_str('1_2_1'), '20130228100026')
        self.assertEqual(self.cmap.get_queuetime_str('2_2_1'), None)

        self.assertTrue(self.cmap.is_right_queuekey('1_2_1', 'secretstring'))
        self.assertFalse(self.cmap.is_right_queuekey('1_2_1', 'invalidstr'))
        self.assertFalse(self.cmap.is_right_queuekey('1_2_1', ''))
        self.assertFalse(self.cmap.is_right_queuekey('1_2_1', None))

        self.assertFalse(self.cmap.is_right_queuekey('2_2_1', 'secretstring'))
        self.assertFalse(self.cmap.is_right_queuekey('2_2_1', 'invalidstr'))
        self.assertFalse(self.cmap.is_right_queuekey('2_2_1', ''))
        self.assertFalse(self.cmap.is_right_queuekey('2_2_1', None))

    def test_get_npoints(self):
        # Set the correctmap properties for 4 inputs
        # 1) correct, 5 points
        # 2) correct, None points
        # 3) incorrect, 5 points
        # 4) incorrect, None points
        # 5) correct, 0 points
        # 4) partially correct, 2.5 points
        # 5) partially correct, None points
        self.cmap.set(
            answer_id='1_2_1',
            correctness='correct',
            npoints=5.3
        )

        self.cmap.set(
            answer_id='2_2_1',
            correctness='correct',
            npoints=None
        )

        self.cmap.set(
            answer_id='3_2_1',
            correctness='incorrect',
            npoints=5
        )

        self.cmap.set(
            answer_id='4_2_1',
            correctness='incorrect',
            npoints=None
        )

        self.cmap.set(
            answer_id='5_2_1',
            correctness='correct',
            npoints=0
        )

        self.cmap.set(
            answer_id='6_2_1',
            correctness='partially-correct',
            npoints=2.5
        )

        self.cmap.set(
            answer_id='7_2_1',
            correctness='partially-correct',
            npoints=None
        )

        # Assert that we get the expected points
        # If points assigned --> npoints
        # If no points assigned and correct --> 1 point
        # If no points assigned and partially correct --> 1 point
        # If no points assigned and incorrect --> 0 points
        self.assertEqual(self.cmap.get_npoints('1_2_1'), 5.3)
        self.assertEqual(self.cmap.get_npoints('2_2_1'), 1)
        self.assertEqual(self.cmap.get_npoints('3_2_1'), 5)
        self.assertEqual(self.cmap.get_npoints('4_2_1'), 0)
        self.assertEqual(self.cmap.get_npoints('5_2_1'), 0)
        self.assertEqual(self.cmap.get_npoints('6_2_1'), 2.5)
        self.assertEqual(self.cmap.get_npoints('7_2_1'), 1)

    def test_set_overall_message(self):

        # Default is an empty string string
        self.assertEqual(self.cmap.get_overall_message(), "")

        # Set a message that applies to the whole question
        self.cmap.set_overall_message("Test message")

        # Retrieve the message
        self.assertEqual(self.cmap.get_overall_message(), "Test message")

        # Setting the message to None --> empty string
        self.cmap.set_overall_message(None)
        self.assertEqual(self.cmap.get_overall_message(), "")

    def test_update_from_correctmap(self):
        # Initialize a CorrectMap with some properties
        self.cmap.set(
            answer_id='1_2_1',
            correctness='correct',
            npoints=5,
            msg='Test message',
            hint='Test hint',
            hintmode='always',
            queuestate={
                'key': 'secretstring',
                'time': '20130228100026'
            }
        )

        self.cmap.set_overall_message("Test message")

        # Create a second cmap, then update it to have the same properties
        # as the first cmap
        other_cmap = CorrectMap()
        other_cmap.update(self.cmap)

        # Assert that it has all the same properties
        self.assertEqual(
            other_cmap.get_overall_message(),
            self.cmap.get_overall_message()
        )

        self.assertEqual(
            other_cmap.get_dict(),
            self.cmap.get_dict()
        )

    def test_update_from_invalid(self):
        # Should get an exception if we try to update() a CorrectMap
        # with a non-CorrectMap value
        invalid_list = [None, "string", 5, datetime.datetime.today()]

        for invalid in invalid_list:
            with self.assertRaises(Exception):
                self.cmap.update(invalid)
