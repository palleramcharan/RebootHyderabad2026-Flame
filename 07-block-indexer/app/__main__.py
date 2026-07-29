import sys
from export_service import BlockchainExportService

if __name__ == "__main__":
    svc = BlockchainExportService()
    if "--rebuild" in sys.argv:
        svc.rebuild_all()
    elif "--once" in sys.argv:
        svc.sync_once()
    else:
        svc.run_forever()
