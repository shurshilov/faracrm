# # Copyright 2025 FARA CRM
# # Attachments module - Cron jobs for sync

# import logging
# from backend.base.system.cron.worker import cron_job

# logger = logging.getLogger(__name__)


# @cron_job(
#     name="attachments_one_way_sync",
#     schedule="0 2 * * *",  # Every day at 2:00 AM
#     description="Sync attachments from FARA to cloud storage",
# )
# async def attachments_one_way_sync():
#     """
#     One-way sync cron job.
#     Syncs attachments from FARA to cloud storage.
#     """
#     from backend.base.crm.attachments.models.attachments_storage import (
#         AttachmentStorage,
#     )

#     logger.info("Cron: Starting one-way attachments sync")
#     await AttachmentStorage.start_one_way_sync()
#     logger.info("Cron: Completed one-way attachments sync")


# @cron_job(
#     name="attachments_two_way_sync",
#     schedule="0 3 * * *",  # Every day at 3:00 AM
#     description="Sync attachments between FARA and cloud storage (two-way)",
# )
# async def attachments_two_way_sync():
#     """
#     Two-way sync cron job.
#     Syncs attachments in both directions.
#     """
#     from backend.base.crm.attachments.models.attachments_storage import (
#         AttachmentStorage,
#     )

#     logger.info("Cron: Starting two-way attachments sync")
#     await AttachmentStorage.start_two_way_sync()
#     logger.info("Cron: Completed two-way attachments sync")


# @cron_job(
#     name="attachments_routes_sync",
#     schedule="0 4 * * *",  # Every day at 4:00 AM
#     description="Sync attachment routes and folder structure",
# )
# async def attachments_routes_sync():
#     """
#     Routes sync cron job.
#     Syncs folder structure and moves files between routes.
#     """
#     from backend.base.crm.attachments.models.attachments_storage import (
#         AttachmentStorage,
#     )

#     logger.info("Cron: Starting routes sync")
#     await AttachmentStorage.start_routes_sync()
#     logger.info("Cron: Completed routes sync")
