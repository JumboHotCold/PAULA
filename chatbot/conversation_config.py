"""Validated, immutable conversation copy/recognition data, loaded once per worker."""
from functools import lru_cache
import json
from pathlib import Path
import re
from types import MappingProxyType

CONFIG_PATH = Path(__file__).with_name('config') / 'conversation.json'


def validate_conversation_config(data):
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported conversation config schema')
    replies, social = data['replies'], data['social']
    required = {'identity', 'capabilities', 'greeting', 'thanks', 'chat_clarification'}
    if not required.issubset(replies):
        raise ValueError('Required conversation replies are missing')
    if not {'identity', 'capabilities', 'greeting', 'wellbeing', 'thanks'}.issubset(social['fast_patterns']):
        raise ValueError('Required local intent patterns are missing')
    for languages in replies.values():
        if not {'en', 'fil'}.issubset(languages):
            raise ValueError('Conversation replies require English and Filipino copy')
        for values in languages.values():
            if not isinstance(values, list) or not values or not all(isinstance(value, str) and value.strip() for value in values):
                raise ValueError('Conversation replies must be nonempty text lists')
    for kind, examples in data['semantic']['exemplars'].items():
        if kind not in replies and kind != 'knowledge':
            raise ValueError('Unknown semantic intent')
        if not isinstance(examples, list) or not examples or not all(isinstance(value, str) and value.strip() for value in examples):
            raise ValueError('Semantic examples must be nonempty text lists')
    if 'knowledge' not in data['semantic']['exemplars']:
        raise ValueError('The semantic knowledge guard is required')
    for kind, pattern in social['fast_patterns'].items():
        if kind not in replies:
            raise ValueError('Unknown local intent')
        re.compile(pattern, re.I)
    re.compile(social['suffix_pattern'])
    for kind, forms in social['forms'].items():
        if kind not in replies or not isinstance(forms, list) or not forms or not all(isinstance(value, str) and value.strip() for value in forms):
            raise ValueError('Invalid social forms')
    for alias, kind in social['abbreviations'].items():
        if not isinstance(alias, str) or not alias or kind not in replies:
            raise ValueError('Invalid social abbreviation')
    for language in ('en', 'fil'):
        intros = data['framing']['intros'][language]
        if not isinstance(intros, list) or not intros or not all(isinstance(value, str) and value.strip() for value in intros):
            raise ValueError('Invalid response framing')
    for languages in data['framing']['acknowledgements'].values():
        if not all(isinstance(languages.get(language), str) and languages[language].strip() for language in ('en', 'fil')):
            raise ValueError('Invalid social acknowledgements')


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@lru_cache(maxsize=1)
def conversation_config():
    data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    validate_conversation_config(data)
    return _freeze(data)
