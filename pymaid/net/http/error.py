from pymaid.error import ErrorManager

HttpError = ErrorManager.create_manager('HttpError')
HttpError.add_error('BadRequest', '', code=400)
