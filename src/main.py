import asyncio
from viam.module.module import Module
try:
    from models.service import Service
except ModuleNotFoundError:
    # when running as local module with run.sh
    from .models.service import Service


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
