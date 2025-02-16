from datetime import datetime, time

# from django.utils import timezone
import pytz
from celery import chain, group, shared_task

from .save_crawler_status import update_code_execution_state
from .task_diarhamrah_crawl import diarhamrah_crawler
from .task_digikala_crawl import digikala_crawler

# Crawlers
from .task_hamrahtel_graphql_crawl import hamrahtel_crawler
from .task_kasrapars_crawl import kasrapars_crawler
from .task_mobile140_crawl import mobile140_crawler
from .task_saymandigital_crawl import saymandigital_crawler
from .task_taavrizh_crawl import taavrizh_crawler
from .task_tecnolife_crawl import tecnolife_crawler
from .task_tellstar_crawl import tellstar_crawler

# from .task_digikala_crawl import digikala_crawler

# Define your tasks
# @shared_task
# def task_a():
#         raise ValueError("Task A error")

# @shared_task
# def task_B():
#     print("Task B executed")
#     # time.sleep(10)

# @shared_task
# def task_C():
#     print("Task C executed")
#     # time.sleep(10)

# @shared_task
# def error_handler(request, exec, traceback):
#     try:
#         print(traceback)
#         print(request.id)
#         print('Error', exec)
#     except:
#         print('hello')

local_tz = pytz.timezone("Asia/Tehran")


# Define a task to chain them and then call itself to loop
# @shared_task
# def loop_tasks():
#     # current_time = datetime.now().time()
#     current_time_utc = datetime.now(pytz.utc)
#     current_time_local = current_time_utc.astimezone(local_tz).time()

#     start_time = time(0,0) # 00:00 midnight
#     end_time = time(8, 0) #‌ 08:00  Am
#     # print(current_time_local)
#     # print(start_time)
#     # print(end_time)
#     # if start_time <= current_time_local <= end_time:
#     #     print("Skipping task execution from 00:00 to 08:00")

#     #     loop_tasks.apply_async(countdown=60 * 60)

#     print("Starting a new iteration of the task chain")
#     # Define the chain of tasks
#     task_group = group(
#         digikala_crawler.si().on_error(error_handler.s()),
# tecnolife_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
# diarhamrah_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
# hamrahtel_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
# saymandigital_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
# mobile140_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
# taavrizh_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
# tellstar_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
# kasrapars_crawler.si().set(countdown=60 * 2).on_error(error_handler.s()),
#     )

#     #     return

#     # task_chain = chain(
#     #     # digikala_crawler.si(),
#     #     task_a.si().on_error(error_handler.s()).set(countdown=5),
#     #     task_B.si().on_error(error_handler.s()).set(countdown=5),
#     #     task_C.si().on_error(error_handler.s()).set(countdown=5),

#     # )

#     task_chord = chord(task_group)(loop_tasks.si())

#     # Optionally, apply_async for scheduling it
#     # task_chord()
#     # task_group.apply_async(link=loop_tasks.si())


# @shared_task
# def start_next_group(group_name):
#     if group_name == 'group1':
#         group(
#             hamrahtel_crawler.s().set(queue='group1_queue'),
#             tellstar_crawler.s().set(queue='group1_queue'),
#             taavrizh_crawler.s().set(queue='group1_queue'),
#         ).apply_async(link=start_next_group.s('group1'), countdown=10)  # Restart group1 after 10 seconds
#     elif group_name == 'group2':
#         group(
#             tecnolife_crawler.s().set(queue='group2_queue'),
#             mobile140_crawler.s().set(queue='group2_queue'),
#             saymandigital_crawler.s().set(queue='group2_queue'),
#         ).apply_async(link=start_next_group.s('group2'), countdown=10)  # Restart group2 after 10 seconds
#     elif group_name == 'group3':
#         group(
#             digikala_crawler.s().set(queue='group3_queue'),
#             diarhamrah_crawler.s().set(queue='group3_queue'),
#             kasrapars_crawler.s().set(queue='group3_queue'),
#         ).apply_async(link=start_next_group.s('group1'), countdown=10)

# @shared_task
# def start_next_group(group_name):
#     if group_name == 'group1':
#         header = [
#             hamrahtel_crawler.s().set(queue='group1_queue'),
#             tellstar_crawler.s().set(queue='group1_queue'),
#             taavrizh_crawler.s().set(queue='group1_queue'),
#         ]
#         # Create a chord with the header tasks and a callback to start the next group
#         chord(header)(start_next_group.s('group1'))  # Will restart group1 after all tasks in group1 finish
#     elif group_name == 'group2':
#         header = [
#             tecnolife_crawler.s().set(queue='group2_queue'),
#             mobile140_crawler.s().set(queue='group2_queue'),
#             saymandigital_crawler.s().set(queue='group2_queue'),
#         ]
#         chord(header)(start_next_group.s('group2'))  # Will restart group2 after all tasks in group2 finish
#     elif group_name == 'group3':
#         header = [
#             digikala_crawler.s().set(queue='group3_queue'),
#             diarhamrah_crawler.s().set(queue='group3_queue'),
#             kasrapars_crawler.s().set(queue='group3_queue'),
#         ]
#         chord(header)(start_next_group.s('group1'))


@shared_task
def error_handler(task_id, exc, traceback, site_name):

    error_message = str(traceback.format_exc())
    update_code_execution_state(site_name, False, error_message)
    print(f"Error {error_message}")


@shared_task
def start_all_crawlers(*args, **kwargs):
    REST_TIME = 1 * 60  # secends
    tasks = group(
        # Group 1 crawlers
        hamrahtel_crawler.si().on_error(error_handler.s("Hamrahtel")),
        saymandigital_crawler.si()
        .set(countdown=REST_TIME)
        .on_error(error_handler.s("Saymandigital")),
        digikala_crawler.si()
        .set(countdown=REST_TIME)
        .on_error(error_handler.s("Digikala")),
        tecnolife_crawler.si()
        .set(countdown=REST_TIME)
        .on_error(error_handler.s("Tecnolife")),
        diarhamrah_crawler.si()
        .set(countdown=REST_TIME)
        .on_error(error_handler.s("Diarhamrah")),
        mobile140_crawler.si()
        .set(countdown=REST_TIME)
        .on_error(error_handler.s("Mobile140")),
        taavrizh_crawler.si()
        .set(countdown=REST_TIME)
        .on_error(error_handler.s("Taavrizh")),
        tellstar_crawler.si()
        .set(countdown=REST_TIME)
        .on_error(error_handler.s("Tellstar")),
    )

    # Execute all tasks in parallel and restart when finished
    # task_chain.apply_async(link=start_all_crawlers.si(), countdown=5 * 60)
    # task_chain = chain(tasks, start_all_crawlers.si())
    # task_chain.apply_async()
    tasks.apply_async()
    return "Group tasks started again.###################################"
    
