"""Regression: Atlas TLS failures cannot prevent startup or hide lost chats."""
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from pymongo.errors import ServerSelectionTimeoutError

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import app as backend
from chat_store import MongoChatStore

client, collection = Mock(), Mock()
client.__getitem__ = Mock(return_value=Mock(chats=collection))
collection.create_index.side_effect = ServerSelectionTimeoutError('SSL handshake failed: TLSV1_ALERT_INTERNAL_ERROR')
with patch('pymongo.MongoClient', return_value=client) as factory:
    store = MongoChatStore('mongodb://unreachable.invalid')
    factory.assert_not_called()
    with patch.object(backend, 'store', store), patch.object(backend.assistant_service,'complete') as complete:
        browser = backend.app.test_client()
        assert browser.get('/health').status_code == 200
        assert browser.get('/').status_code == 200
        for response in [browser.get('/api/history'),browser.get('/api/storage/status'),
                         browser.delete('/api/history'),browser.post('/api/chat',json={
                             'language':'en','messages':[{'role':'user','content':'Help with my crop'}]})]:
            assert response.status_code == 503
            assert response.json == {'error':'storageError'}
        complete.assert_not_called()
        options = factory.call_args.kwargs
        assert options['tls'] and options['tlsCAFile']
        assert options['tlsAllowInvalidCertificates'] is False
        assert options['tlsAllowInvalidHostnames'] is False
        # Recovery retries index creation without requiring a process restart.
        collection.create_index.side_effect = None
        collection.find_one.return_value = None
        assert browser.get('/api/storage/status').json['ready'] is True
        assert browser.get('/api/history').json == {'messages':[]}
print('PASS: deferred connection, TLS verification, safe 503s, no unsaved model turn, recovery without restart')
