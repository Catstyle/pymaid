from pymaid.error import ErrorManager

HttpError = ErrorManager()
HttpError.add_error('BadRequest', '', code=400)
