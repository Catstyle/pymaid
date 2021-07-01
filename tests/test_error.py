from unittest import TestCase

from pymaid import error


class ErrorTest(TestCase):

    def setUp(self):
        error.ErrorManager.managers.clear()
        error.ErrorManager.codes.clear()

    def test_base(self):
        self.assertIsNone(error.BaseEx.code)
        self.assertEqual(error.BaseEx.message, 'BaseEx')

        class Error1(error.Error):
            code = 'Error1'
            message = '{}'
        self.assertEqual(Error1.__module__, __name__)

    def test_error(self):
        class Error1(error.Error):
            code = 'Error1'
            message = '{}'

        self.assertEqual(Error1.code, 'Error1')
        self.assertEqual(Error1.message, '{}')

        ex = Error1('Oops', number=1, data={'name': 'Whatever'})
        self.assertEqual(ex.code, 'Error1')
        self.assertEqual(ex.message, 'Oops')
        self.assertDictEqual(ex.data, {'name': 'Whatever'})
        self.assertEqual(
            str(ex),
            "[ERROR][code|Error1][message|Oops][data|{'name': 'Whatever'}]"
        )

        self.assertIsInstance(ex, error.Error)
        self.assertIsInstance(ex, error.BaseEx)
        self.assertNotIsInstance(ex, error.Warning)

    def test_warning(self):
        class Warning1(error.Warning):
            code = 'Warning1'
            message = '{}'

        self.assertEqual(Warning1.code, 'Warning1')
        self.assertEqual(Warning1.message, '{}')

        ex = Warning1('Oops', number=1, data={'age': 18})
        self.assertEqual(ex.code, 'Warning1')
        self.assertEqual(ex.message, 'Oops')
        self.assertDictEqual(ex.data, {'age': 18})
        self.assertEqual(
            str(ex), "[WARN][code|Warning1][message|Oops][data|{'age': 18}]"
        )

        self.assertIsInstance(ex, error.Warning)
        self.assertIsInstance(ex, error.BaseEx)
        self.assertNotIsInstance(ex, error.Error)

    def test_manager(self):
        UserError = error.ErrorManager.create_manager('UserError')
        self.assertIn('UserError', error.ErrorManager.managers)

        self.assertDictEqual(UserError.codes, {})
        self.assertDictEqual(UserError.managers, {})

        UserError.add_error('UserNotExist', 'User does not exist')
        self.assertIn('UserError.UserNotExist', UserError.codes)
        self.assertEqual(len(UserError.codes), 1)
        self.assertTrue(issubclass(UserError.UserNotExist, error.Error))
        self.assertTrue(issubclass(UserError.UserNotExist, UserError))

        ex = UserError.UserNotExist(data={'name': 'lucy'})
        self.assertIsInstance(ex, error.Error)
        self.assertIsInstance(ex, UserError)
        self.assertEqual(ex.message, 'User does not exist')
        self.assertDictEqual(ex.data, {'name': 'lucy'})

        with self.assertRaises(error.Error):
            raise ex
        with self.assertRaises(UserError):
            raise ex

        try:
            raise ex
        except UserError.UserNotExist:
            # should catch this exception
            pass

        try:
            raise ex
        except UserError:
            # should catch this exception
            pass

        UserError.add_warning('UserBanned', 'User has been banned')
        self.assertIn('UserError.UserBanned', UserError.codes)
        self.assertEqual(len(UserError.codes), 2)
        self.assertTrue(issubclass(UserError.UserBanned, error.Warning))
        self.assertTrue(issubclass(UserError.UserBanned, UserError))

        ex = UserError.UserBanned(
            data={'reason': 'illegal behaviors', 'until': 2000000000}
        )
        self.assertIsInstance(ex, error.Warning)
        self.assertIsInstance(ex, UserError)
        self.assertEqual(ex.message, 'User has been banned')
        self.assertDictEqual(
            ex.data, {'reason': 'illegal behaviors', 'until': 2000000000}
        )

        with self.assertRaises(error.Warning):
            raise ex
        with self.assertRaises(UserError):
            raise ex

        try:
            raise ex
        except UserError.UserBanned:
            # should catch this exception
            pass

        try:
            raise ex
        except UserError:
            # should catch this exception
            pass

        ProfileError = UserError.create_manager('ProfileError')
        assert ProfileError.__name__ == 'ProfileError'
        self.assertIn('ProfileError', UserError.managers)
        ProfileError.add_warning(
            'IncompleteInfo', 'Please fill in the missing info'
        )

        ex = ProfileError.IncompleteInfo(data={'fields': ['age', 'gender']})
        self.assertIsInstance(ex, error.Warning)
        self.assertIsInstance(ex, ProfileError)
        # yes, ProfileError is managed by UserError
        # and it should be catched by UserError
        self.assertIsInstance(ex, UserError)
        self.assertEqual(ex.code, 'UserError.ProfileError.IncompleteInfo')
        self.assertEqual(ex.message, 'Please fill in the missing info')
        self.assertDictEqual(ex.data, {'fields': ['age', 'gender']})

        with self.assertRaises(error.Warning):
            raise ex
        with self.assertRaises(ProfileError):
            raise ex
        with self.assertRaises(UserError):
            raise ex

        self.assertIsNotNone(
            error.ErrorManager.get_exception('UserError.UserNotExist'),
            error.ErrorManager.codes,
        )
        self.assertIs(
            error.ErrorManager.get_exception('UserError.UserNotExist'),
            UserError.UserNotExist,
        )
        self.assertIsNotNone(
            error.ErrorManager.get_exception(
                'UserError.ProfileError.IncompleteInfo'
            )
        )
        self.assertIs(
            error.ErrorManager.get_exception(
                'UserError.ProfileError.IncompleteInfo'
            ),
            ProfileError.IncompleteInfo,
        )

        assert len(error.ErrorManager.managers) == 1, \
            error.ErrorManager.managers
        assert 'UserError' in error.ErrorManager.managers
        assert 'ProfileError' in UserError.managers

    def test_invalid_action(self):
        UserError = error.ErrorManager.create_manager('Manager')
        UserError.add_error('Error1', 'Manager {} has {number} exceptions')
        with self.assertRaises(ValueError):
            UserError.add_error('Error1', 'Manager {} has {number} exceptions')

        error.ErrorManager.managers.pop('Manager')
        del error.ErrorManager.Manager

    def test_assemble(self):
        class Error1(error.Error):
            code = 'Error1'
            message = 'Error1: {}'
        error.ErrorManager.add('Error1', Error1)
        error.ErrorManager.register(Error1)

        ex = error.ErrorManager.assemble('Error1', 'Error1: assembled', {})
        self.assertIsInstance(ex, Error1)

        ex = error.ErrorManager.assemble(
            'Error2', 'cannot find defination', {}
        )
        self.assertIsInstance(ex, error.Warning)
        self.assertEqual(ex.code, 'Unknown_Error2')
        self.assertEqual(ex.__class__.__name__, 'Unknown_Error2')

    def test_magic_args__message_(self):
        class Error1(error.Error):
            code = 'Error1'
            message = None
        error.ErrorManager.add('Error1', Error1)
        error.ErrorManager.register(Error1)

        ex = Error1()
        self.assertIsInstance(ex, Error1)
        self.assertEqual(ex.code, 'Error1')
        self.assertIsNone(ex.message)

        ex = Error1(_message_='overwrite')
        self.assertIsNotNone(ex.message)
        self.assertEqual(ex.message, 'overwrite')

        ex = error.ErrorManager.assemble('Error1', 'Error1: assembled', {})
        self.assertIsInstance(ex, Error1)
        self.assertEqual(ex.code, 'Error1')
        self.assertEqual(ex.message, 'Error1: assembled')

    def test_magic_args_code(self):
        HttpError = error.ErrorManager()
        HttpError.add_error('BadRequest', None, code=400)

        ex = HttpError.BadRequest()
        self.assertIsInstance(ex, error.Error)
        self.assertEqual(ex.code, 400)
        self.assertIsNone(ex.message)

        ex = HttpError.BadRequest(_message_='missing User-Agent header')
        self.assertEqual(ex.code, 400)
        self.assertEqual(ex.message, 'missing User-Agent header')
