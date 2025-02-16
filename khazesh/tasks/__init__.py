
import os 
from .task_chain_crawls import start_all_crawlers
from .task_diarhamrah_crawl import diarhamrah_crawler
from .task_digikala_crawl import digikala_crawler
from .task_tecnolife_crawl import tecnolife_crawler
from .task_hamrahtel_graphql_crawl import hamrahtel_crawler
from .task_saymandigital_crawl import saymandigital_crawler
from .task_mobile140_crawl import mobile140_crawler
from .task_taavrizh_crawl import taavrizh_crawler
from .task_tellstar_crawl import tellstar_crawler
from .task_kasrapars_crawl import kasrapars_crawler
# def detect_tasks(project_root):
#     tasks = []
#     # file_path = os.path.join(project_root, 'khazesh')
#     file_path = project_root
#     for root, dirs, files in os.walk(file_path):
#         for filename in files:
#             if os.path.basename(root) == 'tasks':
#                 if filename.startswith('task') and filename != '__init__.py' and filename.endswith('.py'):
#                     # task = os.path.join(root, filename)\
#                     task =  filename\
#                         .replace(os.path.dirname(project_root) + '/', '')\
#                         .replace('/', '.')\
#                         .replace('.py', '')
#                     tasks.append(task)
#     return tuple(tasks)
# print("os.path.dirname(os.path.abspath(__file__))", os.path.dirname(os.path.abspath(__file__)))
# print(detect_tasks(os.path.dirname(os.path.abspath(__file__))))
# __all__ = detect_tasks(os.path.dirname(os.path.abspath(__file__)))

__all__ = (
           digikala_crawler, 
           diarhamrah_crawler,
           tecnolife_crawler,
           hamrahtel_crawler,
           saymandigital_crawler,
           mobile140_crawler,
           taavrizh_crawler,
           tellstar_crawler,
           kasrapars_crawler,
           start_all_crawlers,
)