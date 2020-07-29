import dataclasses
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List

from pykmymoney.util import kmmvalue_to_decimal


class XMLDeserializableClass():
    """Base class to parse XML elements in a kmy file"""
    _name_map = {}
    _sub_tags = []
    _sub_tag_attributes = []

    @classmethod
    def from_xml(cls, xml: str):
        fields = {f.name: f for f in dataclasses.fields(cls)
                  if f.default == dataclasses.MISSING
                  and f.default_factory == dataclasses.MISSING}

        for k in cls._name_map.keys():
            assert k in fields.keys(), f"Field {k} is not defined for class {cls} but still is in name_map"
        for k in fields.keys():
            k = cls._name_map.get(k, k)
            assert k in xml.attrib, f"Field {k} is missing in xml. Available attributes: {xml.attrib}"

        # obj = cls(**{key:
        #                  cls.cast_attribute(xml.attrib[cls._name_map.get(key, key)], fields[key])
        #              for key in fields.keys()
        #              })
        kwargs = {}
        for key in fields.keys():
            attrib_name = cls._name_map.get(key, key)
            f = fields[key]
            v = cls.cast_attribute(xml.attrib[attrib_name], f)
            kwargs[key] = v
        obj = cls(**kwargs)

        for attr_name, xml_filter, tag_cls in cls._sub_tags:
            sub_tags = []
            for element in xml.findall(xml_filter):
                sub_tag = tag_cls.from_xml(element)
                sub_tags.append(sub_tag)
            setattr(obj, attr_name, sub_tags)

        fields = {f.name: f for f in dataclasses.fields(cls)}
        for attr_name, xml_filter, sub_attr_name in cls._sub_tag_attributes:
            element = xml.find(xml_filter)
            if element is not None:
                setattr(obj, attr_name, cls.cast_attribute(element.attrib[sub_attr_name], fields[attr_name]))

        return obj

    def public_attributes(self):
        for key in dir(self):
            if not key.startswith('_'):
                value = getattr(self, key)
                if not callable(value):
                    yield key, value

    @staticmethod
    def cast_attribute(raw, field):
        if field.type == date:
            try:
                return date.fromisoformat(raw)
            except ValueError:
                return None
        elif field.type == Decimal:
            return kmmvalue_to_decimal(raw)
        elif field.type == str:
            if len(raw) > 0:
                return str(raw)
            else:
                return None
        else:
            return field.type(raw)


@dataclass
class TransactionSplit(XMLDeserializableClass):
    '''One of the split items in a transaction.

    XML example:
    <SPLIT value="-54/1" account="A000003" id="S0001" action="" bankid="A000003-2009-09-16-adc4d00-1"
    number="" payee="P000092" shares="-54/1" reconcileflag="2" reconciledate="" price="1/1"
    memo="NR151108000 INTERNET KAUFUMSATZ 12.09 17.57 UHR"/>
    '''
    value: Decimal
    account_id: str
    id: str
    action: str
    bank_id: str
    number: str
    payee_id: str
    shares: Decimal
    reconcileflag: str
    reconciledate: date
    price: Decimal
    memo: str
    _name_map = {
        'account_id': 'account',
        'bank_id': 'bankid',
        'payee_id': 'payee'
    }


@dataclass
class Transaction(XMLDeserializableClass):
    """Class for managing the contents of a transaction.

    XML example:
    <TRANSACTION commodity="EUR" id="T000000000000000001" postdate="2006-09-01" entrydate="2012-01-19" memo="">
        <SPLITS>
            <SPLIT value="-30537/25" account="A000110" id="S0001" action="" bankid="" number="" payee=""
            shares="-30537/25" reconcileflag="0" reconciledate="" price="1/1"
            memo="Voraussichtliche Rückzahlung Hannelore"/>
            <SPLIT value="30537/25" account="A000079" id="S0002" action="" bankid="" number="" payee=""
            shares="30537/25" reconcileflag="0" reconciledate="" price="1/1"
            memo="Voraussichtliche Rückzahlung Hannelore"/>
        </SPLITS>
    </TRANSACTION>
    """
    id: str
    commodity: str
    postdate: date  # = date.fromisoformat('1900-01-01')
    entrydate: date
    memo: str

    splits: List[TransactionSplit] = field(default_factory=list)
    _sub_tags = [('splits', 'SPLITS/SPLIT', TransactionSplit)]



class ChildAccountID():
    @staticmethod
    def from_xml(xml):
        return xml.attrib['id']

@dataclass
class Account(XMLDeserializableClass):
    """Class for managing the contents of an account.

    XML example:
    ```xml
    <ACCOUNT currency="EUR" id="AStd::Income" lastreconciled="" lastmodified="" name="Einnahme" institution="" number=""
    type="12" opened="" parentaccount="" description="">
    <SUBACCOUNTS>
        <SUBACCOUNT id="A000070"/>
        <SUBACCOUNT id="A000073"/>
    </SUBACCOUNTS>
    </ACCOUNT>

    <ACCOUNT currency="EUR" id="A000001" lastreconciled="2015-03-25" lastmodified="2017-09-02"
    name="Postbank Gemeinschaftskonto" institution="I000001" number="876555304" type="1" opened="2008-07-05"
    parentaccount="A000025" description="">
        <KEYVALUEPAIRS>
            <PAIR value="DE69700100800876555304" key="iban"/>
            <PAIR value="215;5" key="kmm-iconpos"/>
            <PAIR value="4" key="lastNumberUsed"/>
            <PAIR value="0/1" key="lastStatementBalance"/>
            <PAIR value="yes" key="mm-closed"/>
            <PAIR value="2015-03-25:0/1" key="reconciliationHistory"/>
        </KEYVALUEPAIRS>
    </ACCOUNT>
    """
    # Direct attributes
    name: str
    currency: str
    id: str
    institution_id: str
    type_id: str
    parent_account_id: str

    # Renaming
    _name_map = {
        'institution_id': 'institution',
        'type_id': 'type',
        'parent_account_id': 'parentaccount'
    }

    # From subaccounts
    child_account_ids: List[str] = field(default_factory=list)
    _sub_tags = [('child_account_ids', 'SUBACCOUNTS/SUBACCOUNT', ChildAccountID)]

    # From keyvaluepairs
    last_balance: Decimal = Decimal(0)
    closed: bool = False
    last_imported_transaction_date: date = date.fromisoformat('1900-01-01')
    iban: str = None

    _sub_tag_attributes = [
        ('last_balance', "KEYVALUEPAIRS/PAIR[@key='lastStatementBalance']", 'value'),
        ('closed', "KEYVALUEPAIRS/PAIR[@key='mm-closed']", 'value'),
        ('last_imported_transaction_date', "KEYVALUEPAIRS/PAIR[@key='lastImportedTransactionDate']", 'value'),
        ('iban', "KEYVALUEPAIRS/PAIR[@key='iban']", 'value')
    ]

