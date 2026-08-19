import marisa_trie
from mypy.nodes import Sequence
from sqlmodel import Session, select

from schema import User, UserCreate
from schema.database import get_session


class TypeAhead:
    __instance: TypeAhead | None = None

    @staticmethod
    def getInstance():
        """ Static access method. """
        if TypeAhead.__instance is None:
            TypeAhead()
        return TypeAhead.__instance
    #potential: rank somehow
    trie = marisa_trie.Trie()
    def __init__(self):
        if TypeAhead.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            TypeAhead.__instance = self
        self.build_from_db()

    def build_from_db(self):
        with get_session() as se:
            users:Sequence[User] | None = se.exec(select(User)).all()
            if users is None:
                return
            self.trie = marisa_trie.Trie([user.name for user in users])

    def get_with_prefix(self, prefix:str):
        #get first three?
        return self.trie.prefixes(prefix)

