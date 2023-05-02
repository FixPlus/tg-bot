from __future__ import annotations

import sqlite3
from typing import List, Dict, Any, Type
from repository.abstract_repository import AbstractRepository, T


class SQLiteRepository(AbstractRepository[T]):
    """
    Implements AbstractRepository
    """
    def __init__(self, db_path: str, table_name: str, columns: Dict[str, str],
                 entity_type: Type[T]):
        self.table_name = table_name
        self.columns = columns
        self.pk_name = 'id'
        self.entity_type = entity_type
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        columns_str = ', '.join([f'{name} {datatype}'
                                 for name, datatype in self.columns.items()])
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self.table_name} ({columns_str})")
        self.connection.commit()

    def add(self, obj: T) -> int:
        with self.connection:
            values = [getattr(obj, name) for name in self.columns.keys()]
            values_str = ', '.join(['?' for _ in range(len(values))])
            names = ', '.join(self.columns.keys())
            query = f"INSERT INTO {self.table_name} ({names}) VALUES ({values_str})"
            self.cursor.execute('PRAGMA foreign_keys = ON')
            self.cursor.execute(query, values)
            pk = self.cursor.lastrowid
            assert pk is not None
            setattr(obj, self.pk_name, pk)
            return pk

    def __get_obj(self, row: tuple[Any, ...]) -> T:
        obj_dict = {}
        for i, col_name in enumerate(self.columns):
            obj_dict[col_name] = row[i]
        return self.entity_type(**obj_dict)

    def get(self, pk: int) -> T | None:
        query = f"SELECT * FROM {self.table_name} WHERE ROWID == {pk}"
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        if row:
            ret = self.__get_obj(row)
            return ret
        return None

    def get_all(self, where: Dict[str, Any] | None = None) -> List[T]:
        query = f"SELECT * FROM {self.table_name}"
        if where:
            conditions = [f'{name} = ?' for name in where.keys()]
            query += f" WHERE {' AND '.join(conditions)}"
            self.cursor.execute(query, tuple(where.values()))
        else:
            self.cursor.execute(query)
        rows = self.cursor.fetchall()
        objs = [self.__get_obj(row) for row in rows]
        return objs

    def update(self, obj: T) -> None:
        with self.connection:
            values = [getattr(obj, name) for name in self.columns.keys()]
            assignments = ', '.join([f'{name} = ?' for name in self.columns.keys()])
            query = f"UPDATE {self.table_name} SET {assignments} " \
                    f"WHERE ROWID == {getattr(obj, self.pk_name)}"
            self.cursor.execute(query, values)

    def delete(self, pk: int) -> None:
        with self.connection:
            query = f"DELETE FROM {self.table_name} WHERE  ROWID == {pk}"
            self.cursor.execute(query)