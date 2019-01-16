from unittest import TestCase

from pymaid import error


class ErrorTest(TestCase):

    def test_base(self):
        self.assertIsNone(error.BaseEx.code)
        self.assertEquals(error.BaseEx.message, 'BaseEx')

        class Error1(error.Error):
            code = 1
            message = 'Error1: {}'
        self.assertEquals(Error1.__module__, __name__)

    def test_error(self):
        class Error1(error.Error):
            code = 1
            message = 'Error1: {}'

        self.assertEquals(Error1.code, 1)
        self.assertEquals(Error1.message, 'Error1: {}')

        ex = Error1('Oops', number=1, data={'name': 'Whatever'})
        self.assertEquals(ex.code, 1)
        self.assertEquals(ex.message, 'Error1: Oops')
        self.assertDictEqual(ex.data, {'name': 'Whatever'})
        self.assertEquals(
            str(ex),
            "[ERROR][Error1][code|1][message|Error1: Oops]"
            "[data|{'name': 'Whatever'}]"
        )

        self.assertIsInstance(ex, error.Error)
        self.assertIsInstance(ex, error.BaseEx)
        self.assertNotIsInstance(ex, error.Warning)

    def test_warning(self):
        class Warning1(error.Warning):
            code = 1
            message = 'Warning1: {}'

        self.assertEquals(Warning1.code, 1)
        self.assertEquals(Warning1.message, 'Warning1: {}')

        ex = Warning1('Oops', number=1, data={'age': 18})
        self.assertEquals(ex.code, 1)
        self.assertEquals(ex.message, 'Warning1: Oops')
        self.assertDictEqual(ex.data, {'age': 18})
        self.assertEquals(
            str(ex),
            "[WARN][Warning1][code|1][message|Warning1: Oops]"
            "[data|{'age': 18}]"
        )

        self.assertIsInstance(ex, error.Warning)
        self.assertIsInstance(ex, error.BaseEx)
        self.assertNotIsInstance(ex, error.Error)

    def test_manager(self):
        ErrorManager = error.ErrorManager.create_manager('Manager', 1000)
        self.assertIn('Manager', error.ErrorManager.managers)

        self.assertEquals(ErrorManager.index, 1000)
        self.assertDictEqual(ErrorManager.codes, {})
        self.assertDictEqual(ErrorManager.exceptions, {})
        self.assertDictEqual(ErrorManager.managers, {})

        ErrorManager.add_error(
            'Error1', 1, 'Manager {} has {number} exceptions'
        )
        self.assertIn(1001, ErrorManager.codes)
        self.assertIn('Error1', ErrorManager.exceptions)
        self.assertEquals(len(ErrorManager.codes), 1)
        self.assertEquals(len(ErrorManager.exceptions), 1)

        ex = ErrorManager.Error1('Manager', number=1)
        self.assertIsInstance(ex, error.Error)
        self.assertIsInstance(ex, ErrorManager)
        with self.assertRaises(error.Error):
            raise ex
        with self.assertRaises(ErrorManager):
            raise ex

        ErrorManager.add_warning(
            'Warning1', 2, 'Manager {} has {number} exceptions'
        )
        self.assertIn(1002, ErrorManager.codes)
        self.assertIn('Warning1', ErrorManager.exceptions)
        self.assertEquals(len(ErrorManager.codes), 2)
        self.assertEquals(len(ErrorManager.exceptions), 2)

        ex = ErrorManager.Warning1('Manager', number=2)
        self.assertIsInstance(ex, error.Warning)
        self.assertIsInstance(ex, ErrorManager)
        with self.assertRaises(error.Warning):
            raise ex
        with self.assertRaises(ErrorManager):
            raise ex

        SubManager = ErrorManager.create_manager('SubManager', 1100)
        self.assertIn('SubManager', ErrorManager.managers)
        SubManager.add_warning('SubError', 1, 'emmmmmmm')

        self.assertIsNotNone(error.ErrorManager.get_exception(1001))
        self.assertIs(
            error.ErrorManager.get_exception(1001), ErrorManager.Error1
        )
        self.assertIsNotNone(error.ErrorManager.get_exception(1101))
        self.assertIs(
            error.ErrorManager.get_exception(1101), SubManager.SubError
        )

    def test_invalid_action(self):
        ErrorManager = error.ErrorManager.create_manager('Manager', 1000)
        ErrorManager.add_error(
            'Error1', 1, 'Manager {} has {number} exceptions'
        )
        with self.assertRaises(ValueError):
            ErrorManager.add_error(
                'Error1', 1, 'Manager {} has {number} exceptions'
            )
