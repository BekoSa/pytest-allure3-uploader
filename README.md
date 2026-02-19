# pytest-allure-uploader

Uploads `allure-results` to allure3-docker-service.

## Install

pip install -e .

## Usage

Run tests with allure:
```
pytest --alluredir=allure-results \
  --allure-upload \
  --allure-upload-url http://localhost:8080 \
  --allure-upload-project demo
  --allure-config ./allure.config.mjs
```
## Environment variables

- ALLURE_UPLOAD_URL
- ALLURE_UPLOAD_PROJECT
- ALLURE_RESULTS_DIR
- ALLURE_UPLOAD_TIMEOUT
- ALLURE_CONFIG
