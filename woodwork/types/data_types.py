from typing import AsyncGenerator, Generic, TypeVar, List


class Data:
    def __init__(self, data):
        self.data = data


class Text(Data):
    def __init__(self, data: str):
        super().__init__(data)


class Audio(Data):
    def __init__(self, data):
        super().__init__(data)


class Image(Data):
    def __init__(self, data):
        super().__init__(data)


T = TypeVar("T", bound=Data)


class Stream(Generic[T]):
    def __init__(self, generator: AsyncGenerator[T, None]):
        self._generator = generator

    def __aiter__(self) -> AsyncGenerator[T, None]:
        return self._generator

    @classmethod
    def from_iterable(self, items: List[T]) -> "Stream[T]":
        async def gen():
            for item in items:
                yield item

        return self(gen())
