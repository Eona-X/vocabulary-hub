# Integration-test runner for the vocabulary browser. Pins Python 3.13 to match
# the Prez runtime; pyoxigraph 0.5.3 wheels are prebuilt for it.
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY conftest.py test_vocabulary_browser.py ./

# -p no:cacheprefer clean runs in an ephemeral container; -v for readable output.
CMD ["pytest", "-v", "-p", "no:cacheprovider", "--color=yes"]
