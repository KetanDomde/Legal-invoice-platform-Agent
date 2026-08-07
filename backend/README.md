
```bash

uv python install 3.12
uv python pin 3.12
uv venv
source .venv/Scripts/activate
uv pip install -r requirements.txt

uvicorn app.main:app --reload

```
