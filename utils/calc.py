import numpy as np
import random
from decimal import Decimal, getcontext

from src.config.constants import logger
from src.paradex.market import get_pair_data as get_pair_data_paradex
from src.backpack.market import get_pair_data as get_pair_data_backpack

getcontext().prec = 32

def calc_size(
    nominal_value: int,
    token: str,
    current_price: float
) -> tuple:
    logger.debug(f"Calculating size for token: {token} with nominal value: {nominal_value} USD and current price: {current_price} USD")

    try:
        pair_data_paradex = get_pair_data_paradex(token)
        logger.debug(f"Received Paradex pair data for {token}: {pair_data_paradex}")
    except Exception as e:
        logger.error(f"Failed to retrieve Paradex pair data for {token}: {e}")
        raise

    try:
        pair_data_backpack = get_pair_data_backpack(token)
        logger.debug(f"Received Backpack pair data for {token}: {pair_data_backpack}")
    except Exception as e:
        logger.error(f"Failed to retrieve Backpack pair data for {token}: {e}")
        raise

    min_notional_paradex = float(pair_data_paradex["min_notional"])
    logger.debug(f"Paradex minimum notional value for {token}: {min_notional_paradex}")

    precision_paradex = Decimal(str(pair_data_paradex["order_size_increment"]))
    logger.debug(f"Paradex order size increment (precision) for {token}: {precision_paradex}")

    precision_backpack = Decimal(str(pair_data_backpack["stepSize"]))
    logger.debug(f"Backpack step size (precision) for {token}: {precision_backpack}")

    min_token_amount_paradex = calc_min_token_amount(min_notional_paradex, current_price, precision_paradex)
    logger.debug(f"Minimum token amount for Paradex: {min_token_amount_paradex}")

    min_token_amount_backpack = Decimal(pair_data_backpack["filters"]["quantity"]["minQuantity"])
    logger.debug(f"Minimum token amount for Backpack: {min_token_amount_backpack}")

    try:
        max_token_amount_paradex = resize_amount(
            Decimal(str(nominal_value)) / Decimal(str(current_price)), precision_paradex
        )
        logger.debug(f"Maximum token amount for Paradex: {max_token_amount_paradex}")
    except Exception as e:
        logger.error(f"Error calculating max token amount for Paradex: {e}")
        raise

    try:
        max_token_amount_backpack = resize_amount(
            Decimal(str(nominal_value)) / Decimal(str(current_price)), precision_backpack
        )
        logger.debug(f"Maximum token amount for Backpack: {max_token_amount_backpack}")
    except Exception as e:
        logger.error(f"Error calculating max token amount for Backpack: {e}")
        raise

    if max_token_amount_paradex < min_token_amount_paradex or max_token_amount_backpack < min_token_amount_backpack:
        logger.error(f"Order size is too low ({nominal_value} USD) for token: {token}. "
                     f"Max Paradex amount: {max_token_amount_paradex}, "
                     f"Min Paradex amount: {min_token_amount_paradex}, "
                     f"Max Backpack amount: {max_token_amount_backpack}, "
                     f"Min Backpack amount: {min_token_amount_backpack}")
        raise ValueError("Order size error")
    
    logger.debug(f"Calculation successful for token: {token}. Paradex size: {max_token_amount_paradex}, Backpack size: {max_token_amount_backpack}")
    
    if precision_paradex > precision_backpack:
        return max_token_amount_paradex
    return max_token_amount_backpack



def calc_min_token_amount(
    min_notional: int,
    current_price: float,
    precision: Decimal
) -> Decimal:
    min_amount = Decimal(str(min_notional)) / Decimal(str(current_price))
    return resize_up_amount(min_amount, precision)


def resize_amount(
    amount: Decimal,
    precision: Decimal
) -> Decimal:
    return (amount // precision) * precision


def resize_up_amount(
    amount: Decimal,
    precision: Decimal
) -> Decimal:
    return ((amount + precision - Decimal("1E-32")) // precision) * precision
