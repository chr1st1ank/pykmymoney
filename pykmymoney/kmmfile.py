
import gzip
import pandas as pd
import xml.etree.ElementTree as ET

from collections import deque
from functools import lru_cache

from pykmymoney.kmy import Account, Transaction, TransactionSplit



class KMMFile():
    def __init__(self, uri: object) -> object:
        self.uri = uri

    @staticmethod
    def from_kmy(path: str):
        with gzip.open(path, 'rb') as f:
            file_content = f.read()
        file_content = file_content.decode(encoding='utf-8')

        obj = KMMFile(path)
        obj.xml_root = ET.fromstring(file_content)
        obj._load_xml()
        return obj

    def _load_xml(self):
        # Load transactions
        transactions_dict = {t.id: t for t in
                                 map(Transaction.from_xml, self.xml_root.findall('TRANSACTIONS/TRANSACTION'))}
        for t in transactions_dict.values():
            for s in t.splits:
                s.transaction = t
                s.transaction_id = t.id

        self.transactions = [{k: v for k, v in t.public_attributes()}
                             for t in transactions_dict.values()]
        self.transaction_splits = [{k: v for k, v in s.public_attributes()}
                                   for t in transactions_dict.values() for s in t.splits]

        self.transactions_df = pd.DataFrame.from_records(self.transactions)
        self.transaction_splits_df = pd.DataFrame.from_records(self.transaction_splits).merge(
            self.transactions_df, how='left', left_on='transaction_id', right_on='id'
        )

        # Load accounts
        self.accounts_dict = {}
        for accounts in self.xml_root.findall('ACCOUNTS'):
            for account in accounts.findall('ACCOUNT'):
                a = Account.from_xml(account)
                self.accounts_dict[a.id] = a
        self.accounts_df = pd.DataFrame.from_records([
            {k:v  for k,v in a.public_attributes()}
            for a in self.accounts_dict.values()
        ])
        self.accounts_df['uri'] = self.accounts_df['id'].apply(self.get_account_uri)

    @lru_cache(maxsize=1024)
    def get_account_uri(self, account_id):
        # if not hasattr(self, 'get_account_uri_memo'):
        #     self.__get_account_uri_memo = {}
        # try:
        #     return self.__get_account_uri_memo[account_id]
        # except KeyError:
            uri = deque()
            next_account_id = account_id
            next_account = self.accounts_df.loc[self.accounts_df['id'] == next_account_id]
            while len(next_account) > 0:
                uri.appendleft(next_account['name'].item())
                next_account_id = next_account['parent_account_id'].item()
                next_account = self.accounts_df.loc[self.accounts_df['id'] == next_account_id]
            return ':'.join(uri)
            # retval = ':'.join(uri)
            # self.__get_account_uri_memo[account_id] = retval
            # return retval

    def get_account(self, uri, closed=False):
        uri_parts = uri.split(':')
        if closed:
            accounts_df = self.accounts_df
        else:
            accounts_df = self.accounts_df.loc[~self.accounts_df['closed']]
        parent = accounts_df.query(f'name == "{uri_parts[0]}"')
        if not len(parent):
            return parent
        leaf = parent
        for part in uri_parts[1:]:
            parent = leaf
            parent_id = parent['id'].item()
            if part == '*':
                # Return all subaccounts
                return accounts_df.query(f'parent_account_id == "{parent_id}"')
            if part == '**':
                # Aggregate all subaccounts
                return accounts_df.loc[accounts_df['id'].isin(
                    self.get_account_ids_with_subaccounts(parent_id))]
            leaf = accounts_df.query(f'name == "{part}" and parent_account_id == "{parent_id}"')
            if not len(leaf):
                return leaf
        return leaf

    def get_account_ids_with_subaccounts(self, account_id):
        child_account_ids = self.accounts_df.query(f'parent_account_id == "{account_id}"')
        if len(child_account_ids) == 0:
            return set([account_id])
        else:
            child_account_ids = list(child_account_ids['id'])
            return set([account_id]).union(*[self.get_account_ids_with_subaccounts(i) for i in child_account_ids])

    def get_account_transactions(self, uri):
        account_transactions = self.get_account(uri).merge(
            self.transaction_splits_df, how='left', left_on='id', right_on='account_id'
        ).sort_values(by='postdate')
        return account_transactions.assign(saldo=account_transactions['value'].cumsum())[[
            'name', 'postdate', 'memo_y', 'value', 'saldo'
        ]]

    def get_aggregated_sums(self, uri, agg_level=None, since=None, period='M'):
        """

        :param uri:
        :param agg_level: Level of aggregation (>=1). Per default no aggregation is done.
        :param since:
        :param period: Time period to be grouped by (one of 'Y', 'M')
        :return: pd.DataFrame
        """
        account_transactions = self.get_account(uri).merge(
            self.transaction_splits_df, how='left', left_on='id', right_on='account_id'
        )  # .sort_values(by='postdate')
        account_transactions['postdate'] = pd.to_datetime(account_transactions['postdate'])
        if since is not None:
            since = pd.to_datetime(since)
            account_transactions = account_transactions.loc[account_transactions['postdate'] >= since]
        per = account_transactions['postdate'].dt.to_period(period)
        account_transactions['account_uri'] = account_transactions['id'].apply(self.get_account_uri)
        if agg_level is not None:
            account_transactions['account_uri'] = account_transactions['account_uri'].str.split(':').apply(
                lambda l: ':'.join(l[:agg_level]))
        return account_transactions.groupby(['account_uri', per])['value'].sum().sort_index()
