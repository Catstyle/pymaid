from unittest import TestCase

from pymaid import error


class ErrorTest(TestCase):

    def test_base(self):
        self.assertIsNone(error.BaseEx.code)
        self.assertEqual(error.BaseEx.message, 'BaseEx')

        class Error1(error.Error):
            code = 'Error1'
            message = 'Error1: {}'
        self.assertEqual(Error1.__module__, __name__)

    def test_error(self):
        class Error1(error.Error):
            code = 'Error1'
            message = 'Error1: {}'

        self.assertEqual(Error1.code, 'Error1')
        self.assertEqual(Error1.message, 'Error1: {}')

        ex = Error1('Oops', number=1, data={'name': 'Whatever'})
        self.assertEqual(ex.code, 'Error1')
        self.assertEqual(ex.message, 'Error1: Oops')
        self.assertDictEqual(ex.data, {'name': 'Whatever'})
        self.assertEqual(
            str(ex),
            "[ERROR][code|Error1][message|Error1: Oops]"
            "[data|{'name': 'Whatever'}]"
        )

        self.assertIsInstance(ex, error.Error)
        self.assertIsInstance(ex, error.BaseEx)
        self.assertNotIsInstance(ex, error.Warning)

    def test_warning(self):
        class Warning1(error.Warning):
            code = 'Warning1'
            message = 'Warning1: {}'

        self.assertEqual(Warning1.code, 'Warning1')
        self.assertEqual(Warning1.message, 'Warning1: {}')

        ex = Warning1('Oops', number=1, data={'age': 18})
        self.assertEqual(ex.code, 'Warning1')
        self.assertEqual(ex.message, 'Warning1: Oops')
        self.assertDictEqual(ex.data, {'age': 18})
        self.assertEqual(
            str(ex),
            "[WARN][code|Warning1][message|Warning1: Oops][data|{'age': 18}]"
        )

        self.assertIsInstance(ex, error.Warning)
        self.assertIsInstance(ex, error.BaseEx)
        self.assertNotIsInstance(ex, error.Error)

    def test_manager(self):
        ErrorManager = error.ErrorManager.create_manager('Manager')
        self.assertIn('Manager', error.ErrorManager.managers)

        self.assertDictEqual(ErrorManager.codes, {})
        self.assertDictEqual(ErrorManager.managers, {})

        ErrorManager.add_error(
            'Error1', 'Manager {} has {number} exceptions'
        )
        self.assertIn('Manager.Error1', ErrorManager.codes)
        self.assertEqual(len(ErrorManager.codes), 1)
        self.assertTrue(issubclass(ErrorManager.Error1, error.Error))
        self.assertTrue(issubclass(ErrorManager.Error1, ErrorManager))

        ex = ErrorManager.Error1('Manager', number=1)
        self.assertIsInstance(ex, error.Error)
        self.assertIsInstance(ex, ErrorManager)

        with self.assertRaises(error.Error):
            raise ex
        with self.assertRaises(ErrorManager):
            raise ex

        try:
            raise ex
        except ErrorManager.Error1:
            # should catch this exception
            pass

        try:
            raise ex
        except ErrorManager:
            # should catch this exception
            pass

        ErrorManager.add_warning(
            'Warning1', 'Manager {} has {number} exceptions'
        )
        self.assertIn('Manager.Warning1', ErrorManager.codes)
        self.assertEqual(len(ErrorManager.codes), 2)
        self.assertTrue(issubclass(ErrorManager.Warning1, error.Warning))
        self.assertTrue(issubclass(ErrorManager.Warning1, ErrorManager))

        ex = ErrorManager.Warning1('Manager', number=2)
        self.assertIsInstance(ex, error.Warning)
        self.assertIsInstance(ex, ErrorManager)

        with self.assertRaises(error.Warning):
            raise ex
        with self.assertRaises(ErrorManager):
            raise ex

        try:
            raise ex
        except ErrorManager.Warning1:
            # should catch this exception
            pass

        try:
            raise ex
        except ErrorManager:
            # should catch this exception
            pass

        SubManager = ErrorManager.create_manager('SubManager')
        self.assertIn('SubManager', ErrorManager.managers)
        SubManager.add_warning('SubError', 'emmmmmmm')

        self.assertIsNotNone(
            error.ErrorManager.get_exception('Manager.Error1'),
            error.ErrorManager.codes,
        )
        self.assertIs(
            error.ErrorManager.get_exception('Manager.Error1'),
            ErrorManager.Error1,
        )
        self.assertIsNotNone(
            error.ErrorManager.get_exception('SubManager.SubError')
        )
        self.assertIs(
            error.ErrorManager.get_exception('SubManager.SubError'),
            SubManager.SubError,
        )

    def test_invalid_action(self):
        ErrorManager = error.ErrorManager.create_manager('Manager')
        ErrorManager.add_error(
            'Error1', 'Manager {} has {number} exceptions'
        )
        with self.assertRaises(ValueError):
            ErrorManager.add_error(
                'Error1', 'Manager {} has {number} exceptions'
            )

    def test_assemble(self):
        class Error1(error.Error):
            code = 'Error1'
            message = 'Error1: {}'
        error.ErrorManager.add('Error1', Error1)
        error.ErrorManager.register(Error1)

        ex = error.ErrorManager.assemble('Error1', 'Error1: assembled', {})
        self.assertIsInstance(ex, Error1)

        ex = error.ErrorManager.assemble('Error2', 'cannot find defination', {})
        self.assertIsInstance(ex, error.Warning)
        self.assertEqual(ex.code, 'ErrorManager.Unknown-Error2')
        self.assertEqual(ex.__class__.__name__, 'Unknown-Error2')
