from lazyft import logger
from lazyft.reports import get_hyperopt_repo


def load_pairlist_from_id(id: str):
    logger.debug('loading pairlist from params id {}', id)
    return get_hyperopt_repo().get_by_param_id(id).pairlist
