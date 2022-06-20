class HWPrException(Exception):
    """
    Пользовательский класс исключений для обработки
    API ошибок для Практикум.Домашка
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message
