
import os 

from .task_chain_crawls import (
    start_mobile_crawlers,
    start_laptop_crawlers,
    start_tablet_crawlers,
    start_watch_crawlers,
    start_handsfree_crawlers,
    start_powerbank_crawlers,
    start_charger_crawlers,
    start_speaker_crawlers,
)
# Kasra 
from .task_accessories_watchs_kasra_crawl import accessories_watchs_kasra_crawler
from .task_accessories_handsfree_kasra_crawl import accessories_handsfree_kasra_crawler
from .task_accessories_powerbank_kasra_crawl import accessories_powerbank_kasra_crawler
from .task_accessories_charger_kasra_crawl import accessories_charger_kasra_crawler
from .task_accessories_speaker_kasra_crawl import accessories_speaker_kasra_crawler


# Mobile 140 
from .task_accessories_watchs_mobile140_crawl import accessories_watchs_mobile140_crawler
from .task_accessories_handsfree_mobile140_crawl import accessories_handsfree_mobile140_crawler
from .task_accessories_powerbank_mobile140_crawl import accessories_powerbank_mobile140_crawler
from .task_accessories_charger_mobile140_crawl import accessories_charger_mobile140_crawler
from .task_accessories_speaker_mobile140_crawl import accessories_speaker_mobile140_crawler

# Tecnolife
from .task_accessories_watchs_tecnolife_crawl import accessories_watchs_tecnolife_crawler
from .task_accessories_handsfree_tecnolife_crawl import accessories_handsfree_tecnolife_crawler
from .task_accessories_powerbank_tecnolife_crawl import accessories_powerbank_tecnolife_crawler
from .task_accessories_charger_tecnolife_crawl import accessories_charger_tecnolife_crawler
from .task_accessories_speaker_tecnolife_crawl import accessories_speaker_tecnolife_crawler


# Hamrahtel
from .task_accessories_watchs_hamrahtel_crawl import accessories_watchs_hamrahtel_crawler
from .task_accessories_handsfree_hamrahtel_crawl import accessories_handsfree_hamrahtel_crawler
from .task_accessories_powerbank_hamrahtel_crawl import accessories_powerbank_hamrahtel_crawler
from .task_accessories_charger_hamrahtel_crawl import accessories_charger_hamrahtel_crawler
from .task_accessories_speaker_hamrahtel_crawl import accessories_speaker_hamrahtel_crawler


# Digikala
from .task_accessories_watchs_digikala_crawl import accessories_watchs_digikala_crawler
from .task_accessories_handsfree_digikala_crawl import accessories_handsfree_digikala_crawler
from .task_accessories_powerbank_digikala_crawl import accessories_powerbank_digikala_crawler
from .task_accessories_speaker_digikala_crawl import accessories_speaker_digikala_crawler
from .task_accessories_charger_digikala_crawl import accessories_charger_digikala_crawler





# Mobile
from .task_kassa_crawl import kassa_crawler
from .task_mobomin_crawl import mobomin_crawler
from .task_digikala_crawl import digikala_crawler
from .task_tecnolife_crawl import tecnolife_crawler
from .task_hamrahtel_graphql_crawl import hamrahtel_crawler
from .task_saymandigital_crawl import saymandigital_crawler
from .task_mobile140_crawl import mobile140_crawler
from .task_tellstar_crawl import tellstar_crawler


# Tablet
from .task_tablet_hamrahtel_graphql_crawl import tablet_hamrahtel_crawler
from .task_tablet_mobile140_crawl import tablet_mobile140_crawler
from .task_tablet_kassa_crawl import tablet_kassa_crawler
from .task_tablet_digikala_crawl import tablet_digikala_crawler
from .task_tablet_tecnolife_crawl import tablet_tecnolife_crawler
from .task_tablet_darsoo_crawl import tablet_darsoo_crawler
from .task_tablet_etminantel_crawl import tablet_etminantel_crawler


# LapTop
from .task_laptop_tecnolife_crawl import laptop_tecnolife_crawler
from .task_laptop_hamrahtel_crawl import laptop_hamrahtel_crawler
from .task_laptop_digikala_crawl import laptop_digikala_crawler
from .task_laptop_etminantel_ceawl import laptop_etminantel_crawler






__all__ = (
    # Mobile
    digikala_crawler,
    mobile140_crawler,
    tecnolife_crawler,
    saymandigital_crawler,
    tellstar_crawler,
    kassa_crawler,
    hamrahtel_crawler,
    mobomin_crawler,


    # Tablet
    tablet_hamrahtel_crawler, 
    tablet_mobile140_crawler,
    tablet_kassa_crawler,
    tablet_digikala_crawler,
    tablet_tecnolife_crawler,
    tablet_darsoo_crawler,
    tablet_etminantel_crawler,
    
    
    # Laptop
    laptop_tecnolife_crawler,
    laptop_hamrahtel_crawler,
    laptop_digikala_crawler,
    tablet_etminantel_crawler,
    

    accessories_watchs_kasra_crawler,    # kasra
    accessories_handsfree_kasra_crawler, # kasra
    accessories_powerbank_kasra_crawler, # kasra
    accessories_charger_kasra_crawler,   # kasra
    accessories_speaker_kasra_crawler,   # kasra
    
    accessories_watchs_mobile140_crawler,     # Mobile 140
    accessories_handsfree_mobile140_crawler,  # Mobile 140
    accessories_powerbank_mobile140_crawler,  # Mobile 140
    accessories_charger_mobile140_crawler,    # Mobile 140
    accessories_speaker_mobile140_crawler,    # Mobile 140


    accessories_watchs_tecnolife_crawler,     # Tecnolife
    accessories_handsfree_tecnolife_crawler,  # Tecnolife
    accessories_powerbank_tecnolife_crawler,  # Tecnolife
    accessories_charger_tecnolife_crawler,    # Tecnolife
    accessories_speaker_tecnolife_crawler,    # Tecnolife

    accessories_watchs_hamrahtel_crawler,     # Hamrahtel
    accessories_handsfree_hamrahtel_crawler,  # Hamrahtel
    accessories_powerbank_hamrahtel_crawler,  # Hamrahtel
    accessories_charger_hamrahtel_crawler,    # Hamrahtel
    accessories_speaker_hamrahtel_crawler,    # Hamrahtel

    accessories_watchs_digikala_crawler,     # Digikala
    accessories_handsfree_digikala_crawler,  # Digikala
    accessories_powerbank_digikala_crawler,  # Digikala
    accessories_charger_digikala_crawler,    # Digikala
    accessories_speaker_digikala_crawler,    # Digikala


    # Main task starters
    start_mobile_crawlers,
    start_laptop_crawlers,
    start_tablet_crawlers,
    start_watch_crawlers,
    start_handsfree_crawlers,
    start_powerbank_crawlers,
    start_charger_crawlers,
    start_speaker_crawlers,
)