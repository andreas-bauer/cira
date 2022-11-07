import pytest

from fastapi.testclient import TestClient

from src import app
from src.api.service import CiraServiceMock

sentence = "If the button is pressed then the system shuts down."
API_URL = 'http://localhost:8000/api/'

@pytest.fixture(scope="module")
def client() -> TestClient:
    app.cira = CiraServiceMock()
    client = TestClient(app.app)
    return client


@pytest.mark.unit
def test_routes(client):
    response = client.get(f'{API_URL}')
    assert response.status_code == 200

    routes = response.json()
    assert len(routes) >= 4


@pytest.mark.unit
def test_health(client):
    response = client.get(f'{API_URL}health')

    assert response.status_code == 200
    assert response.json() == {'status': 'up'}


@pytest.mark.unit
def test_classification(client):
    response = client.get(
        f'{API_URL}classify', json={"sentence": sentence})

    assert response.status_code == 200
    assert response.json() == {'causal': True, 'confidence': 0.99}


@pytest.mark.unit
def test_labels(client):
    response = client.get(
        f'{API_URL}label', json={"sentence": sentence})

    assert response.status_code == 200
    assert response.json() == {'labels': [
        {'id': 'L1', 'name': 'Variable', 'begin': 10, 'end': 20, 'parent': None}]}


@pytest.mark.unit
def test_graph(client):
    response = client.get(
        f'{API_URL}graph', json={"sentence": sentence})

    assert response.status_code == 200
    assert response.json() == {'graph': {
        'nodes': [
            {'id': 'c', 'variable': 'the button', 'condition': 'is pressed'},
            {'id': 'e', 'variable': 'the system', 'condition': 'shuts down'}
        ],
        'root': 'c',
        'edges': [{'origin': 'c', 'target': 'e', 'negated': False}]
    }}


@pytest.mark.unit
def test_suite(client):
    response = client.get(
        f'{API_URL}testsuite', json={"sentence": sentence, "graph": None})

    assert response.status_code == 200
    assert response.json() == {'suite': {
        'conditions': [{'id': 'c', 'variable': 'the button', 'condition': 'is pressed'}],
        'expected': [{'id': 'c', 'variable': 'the system', 'condition': 'shuts down'}],
        'cases': [{'c': True, 'e': True}, {'c': False, 'e': False}]
    }}
