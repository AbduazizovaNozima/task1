class DomainError(Exception):
    pass


class EmptyQueryError(DomainError):
    pass


class InvalidSpreadsheetError(DomainError):
    pass


class IndexNotReadyError(DomainError):
    pass


class DataInconsistencyError(DomainError):
    pass
