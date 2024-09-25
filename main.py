from oandapyV20 import API
from oandapyV20.exceptions import V20Error
from oandapyV20.endpoints.orders import OrderCreate, Orders, OrderCancel, OrderList, OrderDetails
from oandapyV20.endpoints.positions import OpenPositions, PositionClose
from oandapyV20.endpoints.instruments import Instruments, InstrumentsCandles
from oandapyV20.endpoints.accounts import AccountInstruments, AccountDetails, AccountList
from oandapyV20.endpoints.pricing import PricingInfo
from oandapyV20.endpoints.trades import TradeDetails, TradeCRCDO

import oandapyV20.endpoints.instruments as instruments

from fastapi import FastAPI, WebSocket, HTTPException
from pydantic import BaseModel
from typing import Optional
import telebot
from decimal import Decimal, ROUND_HALF_UP

# telApi = '5837826279:AAFpq6G52pVHJTUmFGB3OODI2ZD70aduqlU'
# telCid = '1118441388'

telApi = '7077011216:AAFlX3PVCpOMTzMoMWnwXpvVJiH3Y4D4O2g'
telCid = '1446316650'

def send_telegram_message(api_token, chat_id, message):
    try:
        textBot = telebot.TeleBot(api_token)
        textBot.send_message(chat_id, "Bot 1\n" + message)
        print("Message sent successfully")
    except Exception as e:
        print(f"An error occurred: {e}")



# textBot = telebot.TeleBot(telApi)

# from typing import Union
# # import json
# import orjson


# run : "uvicorn main:app"

# API credentials
api_token = "9f81fb6bd97df0043ca5f6b164efe108-2ac4f4bae763f5f5c2747f55b7e2c0b8"
account_id = "101-011-25846942-004"

environment = "practice"  # Change to "live" for live trading


# API endpoint
api = API(access_token=api_token, environment="practice")  # Use "live" for live trading




def decimal(symbol):
    para = {
        "instruments": symbol
    }

    # Create the request object for the AccountInstruments endpoint
    r = AccountInstruments(accountID=account_id, params=para)

    # Send the request to the API and print the response
    try:
        response = api.request(r)
        dec = response['instruments'][0]['displayPrecision']
        return int(dec)
    except V20Error as e:
        print(f"Error retrieving candle data: {e}")
        return int(1)

def get_min_tradable_qty(symbol):
    try:
        # Create the request object for the AccountInstruments endpoint
        params = {
            "instruments": symbol
        }
        r = AccountInstruments(accountID=account_id, params=params)
        response = api.request(r)
        minQty = response['instruments'][0]['minimumTradeSize']
        return float(minQty)
    except V20Error as e:
        print(f"Error retrieving instrument information: {e}")
        return None

def round_to_minimum_trade_size(quantity, minimum_trade_size):
    quantity = Decimal(str(quantity))
    minimum_trade_size = Decimal(str(minimum_trade_size))
    return (quantity / minimum_trade_size).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * minimum_trade_size

def calculate_trade_quantity(risk, risk_type, price, symbol):
    # Construct the AccountDetails request
    request = AccountDetails(accountID=account_id)

    # Send the request and parse the response
    try:
        response = api.request(request)
    except V20Error as e:
        print(f"Error retrieving account information: {e}")
        return None

    account_balance = float(response["account"]["balance"])
    margin = float(response["account"]['marginRate'])  # marginRate represents the leverage factor

    minQty = get_min_tradable_qty(symbol)
    if minQty is None:
        return "Could not retrieve minimum tradable quantity."

    # Check for invalid risk_type and risk
    if risk_type is None or risk_type == "":
        return "risk_type cannot be None or an empty string."

    if risk is None or risk == 0:
        return "Risk cannot be None or zero."

    if risk_type not in ['dollar', 'percentage', 'units']:
        return "Invalid risk_type. Must be 'dollar', 'percentage', or 'units'."

    if risk_type == 'dollar' and risk > 0:
        # Convert dollar risk into units
        units = (risk / margin) / price
        return round_to_minimum_trade_size(units, minQty)

    if risk_type == 'percentage' and risk > 0:
        if account_balance is None:
            return "account_balance is required for risk_type 'percentage'."
        else:
            # Convert account percentage into dollar risk
            dollar_risk = (risk / 100) * account_balance
            # Convert dollar risk into units
            units = (dollar_risk / margin) / price
            return round_to_minimum_trade_size(units, minQty)

    if risk_type == 'units' and risk > 0:
        # Directly return the units after validating risk value
        if risk < 0:
            return "Units risk cannot be negative."
        return round_to_minimum_trade_size(risk, minQty)

    return "Invalid input parameters."








# close long trade 

def close_short_positions(instrument=None, Qty=None):
    try:
        messages = []

        # Step 1: Check existing positions
        r = OpenPositions(accountID=account_id)
        response = api.request(r)
        positions = response.get('positions', [])
        # print(positions)

        # Filter positions to find short positions
        if instrument is None:
            # Close all short positions for all instruments
            short_positions = [position for position in positions if float(position['short']['units']) > 0]
        else:
            # Close short positions for a specific instrument
            short_positions = [position for position in positions if position['instrument'] == instrument and float(position['short']['units']) > 0]

        if short_positions:
            # Special case: if Qty and instrument are provided, handle this separately
            if instrument is not None and Qty is not None:
                short_position = short_positions[0]  # Assume there's at least one short position for the instrument
                short_unitA = float(short_position['short']['units'])
                short_units = Qty if abs(short_unitA) >= Qty else short_unitA
                order_data = {
                    "shortUnits": str(short_units)  # Close the short position by buying the specified number of units
                }
                symbol = short_position['instrument']
                close_request = PositionClose(accountID=account_id, instrument=symbol, data=order_data)
                response1 = api.request(close_request)
                # print(response1)

                if 'shortOrderFillTransaction' in response1:
                    order_fill = response1['shortOrderFillTransaction']
                    order_id = response1['shortOrderCreateTransaction']['id']
                    if 'tradesClosed' in order_fill:
                        pnl = float(order_fill['tradesClosed'][0]['realizedPL'])
                    elif 'tradeReduced' in order_fill:
                        pnl = float(order_fill['tradeReduced']['realizedPL'])
                    else:
                        pnl = 0.0
                    msg = f"Successfully closed short position for {symbol} with Order ID {order_id}. Quantity: {short_units}. PnL: {pnl}"
                    messages.append(msg)
                elif 'shortOrderCancelTransaction' in response1:
                    order_cancel = response1['shortOrderCancelTransaction']
                    reason = order_cancel.get('reason', 'No reason provided')
                    if reason == 'MARKET_HALTED':
                        msg = f"Market Halted: Could not close position for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    else:
                        msg = f"Short Market Order Canceled for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    messages.append(msg)
                else:
                    messages.append(f"Unexpected response for {symbol}: {response1}")

                print(msg)
                return "\n".join(messages)

            # Otherwise, loop through all short positions and close them
            for short_position in short_positions:
                short_unitA = float(short_position['short']['units'])
                short_units = short_unitA
                order_data = {
                    "shortUnits": str(short_units)  # Close the short position by buying the same number of units
                }
                symbol = short_position['instrument']
                close_request = PositionClose(accountID=account_id, instrument=symbol, data=order_data)
                response1 = api.request(close_request)
                # print(response1)

                if 'shortOrderFillTransaction' in response1:
                    order_fill = response1['shortOrderFillTransaction']
                    order_id = response1['shortOrderCreateTransaction']['id']
                    if 'tradesClosed' in order_fill:
                        pnl = float(order_fill['tradesClosed'][0]['realizedPL'])
                    elif 'tradeReduced' in order_fill:
                        pnl = float(order_fill['tradeReduced']['realizedPL'])
                    else:
                        pnl = 0.0
                    msg = f"Successfully closed short position for {symbol} with Order ID {order_id}. Quantity: {short_units}. PnL: {pnl}"
                    messages.append(msg)
                elif 'shortOrderCancelTransaction' in response1:
                    order_cancel = response1['shortOrderCancelTransaction']
                    reason = order_cancel.get('reason', 'No reason provided')
                    if reason == 'MARKET_HALTED':
                        msg = f"Market Halted: Could not close position for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    else:
                        msg = f"Short Market Order Canceled for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    messages.append(msg)
                else:
                    messages.append(f"Unexpected response for {symbol}: {response1}")

                print(msg)

            # Refresh positions after all iterations
            r = OpenPositions(accountID=account_id)
            response = api.request(r)
            positions = response.get('positions', [])

            # Update short positions
            if instrument is None:
                short_positions = [position for position in positions if float(position['short']['units']) > 0]
            else:
                short_positions = [position for position in positions if position['instrument'] == instrument and float(position['short']['units']) > 0]

        else:
            if instrument:
                print(f"No short positions to close for {instrument}.")
                return f"No short positions to close for {instrument}."
            else:
                print("No short positions to close for any instrument.")
                return "No short positions to close for any instrument."

        # Return all messages
        return "\n".join(messages)

    except V20Error as e:
        return f"Error: {e}"



def close_long_positions(instrument=None, Qty=None):
    try:
        messages = []

        # Step 1: Check existing positions
        r = OpenPositions(accountID=account_id)
        response = api.request(r)
        positions = response.get('positions', [])
        # print(positions)

        # Filter positions to find long positions
        if instrument is None:
            # Close all long positions for all instruments
            long_positions = [position for position in positions if float(position['long']['units']) > 0]
        else:
            # Close long positions for a specific instrument
            long_positions = [position for position in positions if position['instrument'] == instrument and float(position['long']['units']) > 0]

        if long_positions:
            # Special case: if Qty and instrument are provided, handle this separately
            if instrument is not None and Qty is not None:
                long_position = long_positions[0]  # Assume there's at least one long position for the instrument
                long_unitA = float(long_position['long']['units'])
                long_units = Qty if abs(long_unitA) >= Qty else long_unitA
                order_data = {
                    "longUnits": str(long_units)  # Close the long position by selling the specified number of units
                }
                symbol = long_position['instrument']
                close_request = PositionClose(accountID=account_id, instrument=symbol, data=order_data)
                response1 = api.request(close_request)
                # print(response1)

                if 'longOrderFillTransaction' in response1:
                    order_fill = response1['longOrderFillTransaction']
                    order_id = response1['longOrderCreateTransaction']['id']
                    if 'tradesClosed' in order_fill:
                        pnl = float(order_fill['tradesClosed'][0]['realizedPL'])
                    elif 'tradeReduced' in order_fill:
                        pnl = float(order_fill['tradeReduced']['realizedPL'])
                    else:
                        pnl = 0.0
                    msg = f"Successfully closed long position for {symbol} with Order ID {order_id}. Quantity: {long_units}. PnL: {pnl}"
                    messages.append(msg)
                elif 'longOrderCancelTransaction' in response1:
                    order_cancel = response1['longOrderCancelTransaction']
                    reason = order_cancel.get('reason', 'No reason provided')
                    if reason == 'MARKET_HALTED':
                        msg = f"Market Halted: Could not close position for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    else:
                        msg = f"Long Market Order Canceled for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    messages.append(msg)
                else:
                    messages.append(f"Unexpected response for {symbol}: {response1}")

                print(msg)
                return "\n".join(messages)

            # Otherwise, loop through all long positions and close them
            for long_position in long_positions:
                long_unitA = float(long_position['long']['units'])
                long_units = long_unitA
                order_data = {
                    "longUnits": str(long_units)  # Close the long position by selling the same number of units
                }
                symbol = long_position['instrument']
                close_request = PositionClose(accountID=account_id, instrument=symbol, data=order_data)
                response1 = api.request(close_request)
                # print(response1)

                if 'longOrderFillTransaction' in response1:
                    order_fill = response1['longOrderFillTransaction']
                    order_id = response1['longOrderCreateTransaction']['id']
                    if 'tradesClosed' in order_fill:
                        pnl = float(order_fill['tradesClosed'][0]['realizedPL'])
                    elif 'tradeReduced' in order_fill:
                        pnl = float(order_fill['tradeReduced']['realizedPL'])
                    else:
                        pnl = 0.0
                    msg = f"Successfully closed long position for {symbol} with Order ID {order_id}. Quantity: {long_units}. PnL: {pnl}"
                    messages.append(msg)
                elif 'longOrderCancelTransaction' in response1:
                    order_cancel = response1['longOrderCancelTransaction']
                    reason = order_cancel.get('reason', 'No reason provided')
                    if reason == 'MARKET_HALTED':
                        msg = f"Market Halted: Could not close position for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    else:
                        msg = f"Long Market Order Canceled for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                    messages.append(msg)
                else:
                    messages.append(f"Unexpected response for {symbol}: {response1}")

                print(msg)

            # Refresh positions after all iterations
            r = OpenPositions(accountID=account_id)
            response = api.request(r)
            positions = response.get('positions', [])

            # Update long positions
            if instrument is None:
                long_positions = [position for position in positions if float(position['long']['units']) > 0]
            else:
                long_positions = [position for position in positions if position['instrument'] == instrument and float(position['long']['units']) > 0]

        else:
            if instrument:
                print(f"No long positions to close for {instrument}.")
                return f"No long positions to close for {instrument}."
            else:
                print("No long positions to close for any instrument.")
                return "No long positions to close for any instrument."

        # Return all messages
        return "\n".join(messages)

    except V20Error as e:
        return f"Error: {e}"




def close_all_positions():
    try:
        messages = []

        # Step 1: Check existing positions
        r = OpenPositions(accountID=account_id)
        response = api.request(r)
        positions = response.get('positions', [])

        # Filter positions to find long and short positions
        all_positions = [position for position in positions if float(position['long']['units']) > 0 or float(position['short']['units']) > 0]

        if all_positions:
            for position in all_positions:
                symbol = position['instrument']

                # Close long positions
                if float(position['long']['units']) > 0:
                    long_units = float(position['long']['units'])
                    long_order_data = {
                        "longUnits": str(long_units)  # Close the long position by selling the specified number of units
                    }
                    close_long_request = PositionClose(accountID=account_id, instrument=symbol, data=long_order_data)
                    response1 = api.request(close_long_request)

                    if 'longOrderFillTransaction' in response1:
                        order_fill = response1['longOrderFillTransaction']
                        order_id = response1['longOrderCreateTransaction']['id']
                        if 'tradesClosed' in order_fill:
                            pnl = float(order_fill['tradesClosed'][0]['realizedPL'])
                        elif 'tradeReduced' in order_fill:
                            pnl = float(order_fill['tradeReduced']['realizedPL'])
                        else:
                            pnl = 0.0
                        msg = f"Successfully closed long position for {symbol} with Order ID {order_id}. Quantity: {long_units}. PnL: {pnl}"
                        messages.append(msg)
                    elif 'longOrderCancelTransaction' in response1:
                        order_cancel = response1['longOrderCancelTransaction']
                        reason = order_cancel.get('reason', 'No reason provided')
                        if reason == 'MARKET_HALTED':
                            msg = f"Market Halted: Could not close long position for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                        else:
                            msg = f"Long Market Order Canceled for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                        messages.append(msg)
                    else:
                        messages.append(f"Unexpected response for long position {symbol}: {response1}")

                    print(msg)

                # Close short positions
                if float(position['short']['units']) > 0:
                    short_units = float(position['short']['units'])
                    short_order_data = {
                        "shortUnits": str(short_units)  # Close the short position by buying the specified number of units
                    }
                    close_short_request = PositionClose(accountID=account_id, instrument=symbol, data=short_order_data)
                    response2 = api.request(close_short_request)

                    if 'shortOrderFillTransaction' in response2:
                        order_fill = response2['shortOrderFillTransaction']
                        order_id = response2['shortOrderCreateTransaction']['id']
                        if 'tradesClosed' in order_fill:
                            pnl = float(order_fill['tradesClosed'][0]['realizedPL'])
                        elif 'tradeReduced' in order_fill:
                            pnl = float(order_fill['tradeReduced']['realizedPL'])
                        else:
                            pnl = 0.0
                        msg = f"Successfully closed short position for {symbol} with Order ID {order_id}. Quantity: {short_units}. PnL: {pnl}"
                        messages.append(msg)
                    elif 'shortOrderCancelTransaction' in response2:
                        order_cancel = response2['shortOrderCancelTransaction']
                        reason = order_cancel.get('reason', 'No reason provided')
                        if reason == 'MARKET_HALTED':
                            msg = f"Market Halted: Could not close short position for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                        else:
                            msg = f"Short Market Order Canceled for {symbol}. Order ID: {order_cancel['orderID']}, Reason: {reason}"
                        messages.append(msg)
                    else:
                        messages.append(f"Unexpected response for short position {symbol}: {response2}")

                    print(msg)

            # Refresh positions after all iterations
            r = OpenPositions(accountID=account_id)
            response = api.request(r)
            positions = response.get('positions', [])

            # Update positions
            all_positions = [position for position in positions if float(position['long']['units']) > 0 or float(position['short']['units']) > 0]

        else:
            print("No positions to close for any instrument.")
            return "No positions to close for any instrument."

        # Return all messages
        return "\n".join(messages)

    except V20Error as e:
        return f"Error: {e}"









def print_open_positions(symbol):
    """
    Prints open positions for the given instrument symbol.
    
    Args:
    symbol (str): The instrument symbol to check for open positions.
    """
    try:
        # Step 1: Get the current open positions
        r = OpenPositions(accountID=account_id)
        response = api.request(r)
        positions = response.get('positions', [])

        # Step 2: Find and print the position for the given symbol
        position_to_print = None
        
        for position in positions:
            if position['instrument'] == symbol:
                position_to_print = position
                break
        
        if position_to_print is None:
            print(f"No open position for {symbol} found.")
        else:
            long_units = position_to_print['long']['units']
            short_units = position_to_print['short']['units']
            print(f"Open position for {symbol}:")
            print(f"  Long units: {long_units}")
            print(f"  Short units: {short_units}")
    except V20Error as e:
        print(f"Error retrieving open positions. Error: {e}")




# Open Market Order Function
def send_market_order(quantity, symbol):
    """
    Sends a market order based on the given parameters.
    
    Args:
    order_type (str): Type of order ("MARKET").
    quantity (int): Number of units to buy/sell.
    position_type (str): Type of position ("long" or "short").
    symbol (str, optional): Instrument symbol. Defaults to "GBP_USD".
    """

    # Order details
    order_data = {
        "order": {
            "type": "MARKET",
            "instrument": symbol,
            "units": quantity  # Specify your position size here
        }
    }

    # Place the order
    order_create_request = OrderCreate(accountID=account_id, data=order_data)
    try:
        response = api.request(order_create_request)
        # print(response)
        order_id = response['orderCreateTransaction']['id']
        trade_id = response['orderFillTransaction']['tradeOpened']['tradeID']
        en_price = response['orderFillTransaction']['tradeOpened']['price']
        msg = f"{symbol} Market Order {order_id} placed at {en_price}!"
        print(msg)
        return msg
    except V20Error as e:
        msg = f"Failed to place the maeket order. Error: {str(e)}"
        return msg

def send_limit_order(quantity, symbol, price):
    """
    Sends a limit order based on the given parameters.
    
    Args:
    quantity (int): Number of units to buy/sell.
    symbol (str): Instrument symbol.
    price (float): The price at which to execute the limit order.
    """
    # Determine whether the order is to buy or sell
    units = quantity if quantity > 0 else -abs(quantity)
    
    # Order details
    order_data = {
        "order": {
            "type": "LIMIT",
            "instrument": symbol,
            "units": str(units),  # Specify your position size here
            "price": str(price),  # The price at which the limit order should be executed
            "timeInForce": "GTC",  # Good 'til canceled
            "positionFill": "DEFAULT"  # Fill or kill
        }
    }

    # Place the order
    order_create_request = OrderCreate(accountID=account_id, data=order_data)
    try:
        response = api.request(order_create_request)
        print(response)
        print("Limit order placed successfully!")
        # print("Response:", response)
    except V20Error as e:
        msg = f"Failed to place the limit order. Error: {str(e)}"
        return msg


def send_limit_order_with_tp_sl(quantity, symbol, price, tp_price=None, sl_price=None):
    """
    Sends a limit order with optional take profit and stop loss prices.

    Args:
    quantity (int): Number of units to buy/sell.
    symbol (str): Instrument symbol.
    price (float): The price at which to execute the limit order.
    tp_price (float, optional): The price at which to take profit. Defaults to None.
    sl_price (float, optional): The price at which to stop loss. Defaults to None.
    """
    # Check if price is 0 or None
    if price is None or price == 0:
        return "Price is required to place a limit order."

    # Determine whether the order is to buy or sell
    order_side = "Buy" if quantity > 0 else "Sell"
    units = quantity if quantity > 0 else -abs(quantity)

    # Order details
    order_data = {
        "order": {
            "type": "LIMIT",
            "instrument": symbol,
            "units": str(units),  # Specify your position size here
            "price": str(price),  # The price at which the limit order should be executed
            "timeInForce": "GTC",  # Good 'til canceled
            "positionFill": "DEFAULT",  # Fill or kill
        }
    }

    # Add TP and SL if provided and not zero
    if tp_price and tp_price != 0:
        order_data["order"]["takeProfitOnFill"] = {
            "price": str(tp_price)
        }
    if sl_price and sl_price != 0:
        order_data["order"]["stopLossOnFill"] = {
            "price": str(sl_price)
        }

    # Place the order
    order_create_request = OrderCreate(accountID=account_id, data=order_data)
    try:
        response = api.request(order_create_request)
        order_id = response['orderCreateTransaction']['id']
        return f"{symbol} {order_side} Limit Order ID {order_id} placed successfully!"
    
    except V20Error as e:
        return f"Failed to place the limit order. Error: {e}"



def get_open_limit_orders():
    """Retrieve the list of open limit orders."""
    order_list_request = OrderList(accountID=account_id)
    try:
        response = api.request(order_list_request)
        limit_orders = [order for order in response['orders'] if order['type'] == 'LIMIT']
        return limit_orders
    except V20Error as e:
        return f"Failed to retrieve open orders. Error: {e}"

def cancel_order(order_id):
    """Cancel an order by its ID."""
    order_cancel_request = OrderCancel(accountID=account_id, orderID=order_id)
    try:
        response = api.request(order_cancel_request)
        return response
    except V20Error as e:
        return f"Failed to cancel order {order_id}. Error: {e}"

def cancel_orders_by_price(price, symbol=None):
    """
    Cancel open limit orders that match the given price and optional symbol.

    Args:
    price (float): The price to match against open limit orders.
    symbol (str, optional): The symbol to match against open limit orders. Defaults to None.
    """
    open_orders = get_open_limit_orders()
    if isinstance(open_orders, str):
        return open_orders  # Return error message if failed to retrieve orders

    if symbol:
        matched_orders = [order for order in open_orders if float(order['price']) == float(price) and order['instrument'] == symbol]
    else:
        matched_orders = [order for order in open_orders if float(order['price']) == float(price)]

    if not matched_orders:
        return f"No open limit orders found with price {price}."

    cancelled_orders = []
    for order in matched_orders:
        order_id = order['id']
        cancel_response = cancel_order(order_id)
        if isinstance(cancel_response, str):
            return cancel_response  # Return error message if failed to cancel an order
        cancelled_orders.append(order_id)
    
    return f"Cancelled orders: {', '.join(cancelled_orders)}"



def cancel_pending_buy_orders(symbol=None):
    """
    Cancel all open pending buy orders or buy orders for a specific symbol.

    Args:
    symbol (str, optional): The symbol to match against open limit buy orders. Defaults to None.
    """
    open_orders = get_open_limit_orders()
    if isinstance(open_orders, str):
        return open_orders  # Return error message if failed to retrieve orders
    
    if symbol:
        buy_orders = [order for order in open_orders if order['units'][0] != '-' and order['instrument'] == symbol]
    else:
        buy_orders = [order for order in open_orders if order['units'][0] != '-']  # Buy orders have positive units

    if not buy_orders:
        return "No open pending buy orders found."

    cancelled_orders = []
    for order in buy_orders:
        order_id = order['id']
        cancel_response = cancel_order(order_id)
        if isinstance(cancel_response, str):
            return cancel_response  # Return error message if failed to cancel an order
        cancelled_orders.append(order_id)
    
    return f"Cancelled buy orders: {', '.join(cancelled_orders)}"


def cancel_pending_sell_orders(symbol=None):
    """
    Cancel all open pending sell orders or sell orders for a specific symbol.

    Args:
    symbol (str, optional): The symbol to match against open limit sell orders. Defaults to None.
    """
    open_orders = get_open_limit_orders()
    if isinstance(open_orders, str):
        return open_orders  # Return error message if failed to retrieve orders
    
    if symbol:
        sell_orders = [order for order in open_orders if order['units'][0] == '-' and order['instrument'] == symbol]
    else:
        sell_orders = [order for order in open_orders if order['units'][0] == '-']  # Sell orders have negative units

    if not sell_orders:
        return "No open pending sell orders found."

    cancelled_orders = []
    for order in sell_orders:
        order_id = order['id']
        cancel_response = cancel_order(order_id)
        if isinstance(cancel_response, str):
            return cancel_response  # Return error message if failed to cancel an order
        cancelled_orders.append(order_id)
    
    return f"Cancelled sell orders: {', '.join(cancelled_orders)}"



def cancel_all_pending_orders(symbol=None):
    """
    Cancel all open pending orders or orders for a specific symbol.

    Args:
    symbol (str, optional): The symbol to match against open limit orders. Defaults to None.
    """
    open_orders = get_open_limit_orders()
    if isinstance(open_orders, str):
        return open_orders  # Return error message if failed to retrieve orders
    
    if not open_orders:
        return "No open pending orders found."

    if symbol:
        orders_to_cancel = [order for order in open_orders if order['instrument'] == symbol]
        if not orders_to_cancel:
            return f"No open pending orders found for symbol {symbol}."
    else:
        orders_to_cancel = open_orders

    cancelled_orders = []
    for order in orders_to_cancel:
        order_id = order['id']
        cancel_response = cancel_order(order_id)
        if isinstance(cancel_response, str):
            return cancel_response  # Return error message if failed to cancel an order
        cancelled_orders.append(order_id)
    
    return f"Cancelled orders: {', '.join(cancelled_orders)}"








def send_market_order_with_tp_sl(quantity, symbol, tp_price=None, sl_price=None):
    """
    Sends a market order with optional take profit and stop loss prices.

    Args:
    quantity (int): Number of units to buy/sell. Positive for buy, negative for sell.
    symbol (str): Instrument symbol.
    tp_price (float, optional): The price at which to take profit. Defaults to None.
    sl_price (float, optional): The price at which to stop loss. Defaults to None.
    """

    dec = decimal(symbol)
    # Determine whether the order is to buy or sell
    units = quantity if quantity > 0 else -abs(quantity)
    order_side = "Buy" if quantity > 0 else "Sell"
    # Order details
    order_data = {
        "order": {
            "type": "MARKET",
            "instrument": symbol,
            "units": str(units),  # Specify your position size here
            "timeInForce": "FOK",  # Fill or Kill
        }
    }

    # Add TP and SL if provided
    if tp_price:
        order_data["order"]["takeProfitOnFill"] = {
            "price": str(round(tp_price, dec))
        }
    if sl_price:
        order_data["order"]["stopLossOnFill"] = {
            "price": str(round(sl_price, dec))
        }

    # Place the order
    order_create_request = OrderCreate(accountID=account_id, data=order_data)
    try:
        response = api.request(order_create_request)
        # order_id = response['orderCreateTransaction']['id']
        # return f"{symbol} {order_side} Market Order ID {order_id} placed successfully!"
        if 'orderFillTransaction' in response:
            order_fill = response['orderFillTransaction']
            order_id = response['orderCreateTransaction']['id']
            trade_id = order_fill['tradeOpened']['tradeID']
            en_price = order_fill['tradeOpened']['price']
            order_qty = order_fill['units']
            order_symbol = order_fill['instrument']
            # msg = f"{symbol} {order_side} Market Order {order_id}/{trade_id} Placed @ {en_price}!"
            msg = f"{order_side} Market Order filled. Order ID: {order_id}/{trade_id}, Instrument: {order_symbol}, Qty: {order_qty}, Price: {en_price}"
            print(msg)
            return msg
        elif 'orderCancelTransaction' in response:
            order_cancel = response['orderCancelTransaction']
            msg = f"{order_side} Market Order Canceled. Order ID: {order_cancel['orderID']}, Reason: {order_cancel['reason']}"
            print(msg)
            return msg
        else:
            print("No order fill or cancel transaction found.")
            return msg

        # print(response)
        # order_id = response['orderCreateTransaction']['id']
        # trade_id = response['orderFillTransaction']['tradeOpened']['tradeID']
        # en_price = response['orderFillTransaction']['tradeOpened']['price']
        # msg = f"{symbol} {order_side} Market Order {order_id}/{trade_id} Placed @ {en_price}!"
        # print(msg)
        # return msg


        # print(response)
        # print("Market order placed successfully!")
        # print("Response:", response)
    except V20Error as e:
        msg = f"Failed to place the market order. Error: {str(e)}"
        return msg



def cancel_long_limit_order(symbol):
    try:
        # Step 1: Retrieve open orders
        orders_request = OrderList(accountID=account_id)
        orders_response = api.request(orders_request)
        open_orders = orders_response.get('orders', [])
        
        # Step 2: Find the long limit order for the given symbol
        long_limit_order = None
        for order in open_orders:
            if (order['instrument'] == symbol and 
                order['type'] == 'LIMIT' and 
                int(order['units']) > 0):
                long_limit_order = order
                break
        
        if long_limit_order:
            # Step 3: Cancel the identified long limit order
            order_id = long_limit_order['id']
            cancel_request = OrderCancel(accountID=account_id, orderID=order_id)
            api.request(cancel_request)
            print(f"Canceled long limit order {order_id} successfully.")
        else:
            print(f"No long limit order to cancel for the instrument {symbol}.")
    except V20Error as e:
        msg = f"Failed to place the limit order. Error: {str(e)}"
        return msg


# def cancel_all_pending_orders(symbol):
#     try:
#         # Step 1: Retrieve open orders
#         orders_request = OrderList(accountID=account_id)
#         orders_response = api.request(orders_request)
#         open_orders = orders_response.get('orders', [])
        
#         # Step 2: Find all pending orders for the given symbol
#         pending_orders = [order for order in open_orders if order['instrument'] == symbol]
        
#         if pending_orders:
#             # Step 3: Cancel each identified pending order
#             for order in pending_orders:
#                 order_id = order['id']
#                 cancel_request = OrderCancel(accountID=account_id, orderID=order_id)
#                 api.request(cancel_request)
#                 print(f"Canceled order {order_id} successfully.")
#         else:
#             print(f"No pending orders to cancel for the instrument {symbol}.")
#     except V20Error as e:
#         print("Error:", e)



def get_all_symbols_server():
    """
    Retrieves all available instruments using the OANDA v20 API for a demo account.

    Args:
        api_token (str): Your OANDA API access token.
        account_id (str): Your OANDA demo account ID.

    Returns:
        list: A list of all available instrument symbols.
    """
    all_symbols = []

    # Construct the AccountInstruments request
    request = AccountInstruments(accountID=account_id)

    try:
        # Send the request and parse the response
        response = api.request(request)
        instruments = response.get("instruments", [])

        # Extract symbols from instruments
        all_symbols.extend([instrument["name"] for instrument in instruments])

    except V20Error as e:
        print("V20Error occurred:", e)

    return all_symbols


def get_all_symbols_local():
    return ['USB05Y_USD', 'NZD_HKD', 'USB30Y_USD', 'FR40_EUR', 'CAD_SGD', 'AUD_NZD', 'BCO_USD', 'CAD_CHF', 'XAG_SGD', 
            'XAU_CHF', 'GBP_USD', 'USD_MXN', 'AUD_CAD', 'UK10YB_GBP', 'JP225_USD', 'XAG_CAD', 'NATGAS_USD', 'EUR_DKK', 
            'EUR_CAD', 'USD_HUF', 'DE30_EUR', 'USD_SEK', 'GBP_SGD', 'XPD_USD', 'AUD_JPY', 'ZAR_JPY', 'XAG_JPY', 'ETH_USD', 
            'SGD_JPY', 'GBP_ZAR', 'BTC_USD', 'USD_JPY', 'EUR_TRY', 'EUR_JPY', 'AUD_SGD', 'XAG_NZD', 'WTICO_USD', 'XAG_AUD', 
            'EUR_NZD', 'GBP_HKD', 'CHF_JPY', 'EUR_HKD', 'GBP_CAD', 'XAU_HKD', 'XAU_JPY', 'USD_THB', 'GBP_CHF', 'AUD_CHF', 
            'NZD_CHF', 'ESPIX_EUR', 'AUD_HKD', 'XAG_HKD', 'USD_CHF', 'XAG_CHF', 'BCH_USD', 'CAD_HKD', 'CH20_CHF', 'XAU_CAD', 
            'DE10YB_EUR', 'EUR_PLN', 'SUGAR_USD', 'HKD_JPY', 'UK100_GBP', 'US2000_USD', 'EUR_HUF', 'GBP_PLN', 'USD_SGD', 
            'EUR_SEK', 'XAU_USD', 'GBP_NZD', 'CN50_USD', 'USD_CZK', 'JP225Y_JPY', 'EUR_NOK', 'US30_USD', 'EUR_GBP', 
            'CHF_HKD', 'NZD_JPY', 'XAG_USD', 'EUR_CZK', 'WHEAT_USD', 'XAU_AUD', 'SGD_CHF', 'CORN_USD', 'EUR_CHF', 'NZD_CAD', 
            'USD_CNH', 'XAU_SGD', 'USD_TRY', 'GBP_JPY', 'SPX500_USD', 'EUR_SGD', 'AUD_USD', 'XCU_USD', 'USB02Y_USD', 
            'LTC_USD', 'HK33_HKD', 'USD_NOK', 'XAG_EUR', 'NZD_SGD', 'XAG_GBP', 'USD_CAD', 'USB10Y_USD', 'EU50_EUR', 
            'EUR_AUD', 'TRY_JPY', 'XAU_NZD', 'CAD_JPY', 'USD_ZAR', 'NL25_EUR', 'XAU_XAG', 'XAU_GBP', 'USD_DKK', 'AU200_AUD', 
            'SOYBN_USD', 'NAS100_USD', 'EUR_ZAR', 'USD_PLN', 'GBP_AUD', 'CHINAH_HKD', 'NZD_USD', 'USD_HKD', 'XPT_USD', 
            'SG30_SGD', 'CHF_ZAR', 'XAU_EUR']







def format_symbol2(symbol):
    if "_" not in symbol:
        if len(symbol) < 6:
            raise ValueError("Invalid symbol format")
        
        # Insert underscore before the last three characters
        formatted_symbol = symbol[:-3] + "_" + symbol[-3:]
        return formatted_symbol
    else:
        return symbol


# Example usage:
symbol = "EUR_AUD"
formatted_symbol = format_symbol2(symbol)
# print(formatted_symbol)  # Output: USB30Y_USD


def is_valid_symbol(symbol):
    all_symbols_local = get_all_symbols_local()
    if symbol in all_symbols_local:
        return True
    
    all_symbols_server = get_all_symbols_server()
    return symbol in all_symbols_server

# Example usage:
# print(is_valid_symbol('EUR_USD'))  # Should return True (local)


symbol_to_check = format_symbol2('EURUSD')

# if is_valid_symbol(symbol_to_check):
#     print(f"{symbol_to_check} is a valid symbol.")
# else:
#     print(f"{symbol_to_check} is not a valid symbol.")




app = FastAPI()

####################################################################################################################


# TT : Trade Type  OPEN Or CLOSE 
# TD : Trade Direction BUY Or SELL
# OT : Order Type LIMIT Or MARKET
# CP : Capital 
# TK : Ticker
# LX : leverage X


class Syntax(BaseModel):
    """
    Represents trade order instructions.
    """
    command   :  Optional[str]   = None  # Optional (buymarket, buylimit, sellmarket, selllimit, closebuy, closesell, closeall, cancellimitbyprice, cancelallbuylimit, cancelallselllimit)
    symbol    :  Optional[str]   = None  # Optional stock/currency symbol
    risk      :  Optional[float] = None  # Optional risk amount
    risk_type :  Optional[str]   = None  # Optional risk type (account_percentage/absolute_qty/dollar)
    price     :  Optional[float] = None  # Optional symbol Price
    tp_price  :  Optional[float] = None  # Optional Target Price
    sl_price  :  Optional[float] = None  # Optional Stop-Loss Price



def get_account_balance():

    # Construct the AccountDetails request
    request = AccountDetails(accountID=account_id)

    try:
        # Send the request and parse the response
        response = api.request(request)
        balance = float(response["account"]["balance"])
        # margin_available = float(response["account"]["marginAvailable"])
        leverage = 500/float(response["account"]['marginRate'])  # marginRate represents the leverage factor
        # print(margin_available)
        print(leverage)
        # print(response)
    except V20Error as e:
        print("V20Error occurred:", e)
        balance = None

    return balance

# print(get_account_balance())




@app.get("/")
def root():
    return "Oanda Bot 🚀"


@app.post("/oanda/", tags=['Oanda'])
async def webhook_listener(order : Syntax):
    # recMsg = f"command: {order.command}, symbol: {order.symbol}, risk: {order.risk}, risk_type: {order.risk_type}, price: {order.price}, tp_price: {order.tp_price}, sl_price: {order.sl_price}"
    recMsg = (
    f"command : {order.command}\n"
    f"symbol : {order.symbol}\n"
    f"risk : {order.risk}\n"
    f"risk_type : {order.risk_type}\n"
    f"price : {order.price}\n"
    f"tp_price : {order.tp_price}\n"
    f"sl_price : {order.sl_price}\n")
    send_telegram_message(telApi, telCid, recMsg)
    return recMsg


@app.post("/webhook/", tags=['Webhook'])
async def webhook_listener(order : Syntax):

    recMsg = (
    f"command : {order.command}\n"
    f"symbol : {order.symbol}\n"
    f"risk : {order.risk}\n"
    f"risk_type : {order.risk_type}\n"
    f"price : {order.price}\n"
    f"tp_price : {order.tp_price}\n"
    f"sl_price : {order.sl_price}\n")
    send_telegram_message(telApi, telCid, recMsg)

    ticker = None if order.symbol == None else format_symbol2(str.upper(order.symbol))

    dec = decimal(ticker)

    if not order.command == None :
        if str.lower(order.command) in ['buymarket', 'marketbuy']:

            if is_valid_symbol(ticker):
                Qty = calculate_trade_quantity(order.risk, str.lower('units'), order.price, ticker)
                if isinstance(Qty, str):
                    send_telegram_message(telApi, telCid, Qty)
                    return Qty  # Return the error message
                else:
                    order = send_market_order_with_tp_sl(Qty, ticker, order.tp_price, order.sl_price) #:send_market_order(Qty, ticker)
                    send_telegram_message(telApi, telCid, order)
                    return order  # Return the quantity for the order placement
            else:
                send_telegram_message(telApi, telCid, f"{ticker} is not a valid symbol.")
                return f"{ticker} is not a valid symbol."

        elif str.lower(order.command) in ['buylimit', 'limitbuy']:

            if is_valid_symbol(ticker):
                Qty = calculate_trade_quantity(order.risk, str.lower('units'), order.price, ticker)
                if isinstance(Qty, str):
                    send_telegram_message(telApi, telCid, Qty)
                    return Qty  # Return the error message
                else:
                    order = send_limit_order_with_tp_sl(Qty, ticker, order.price, order.tp_price, order.sl_price) #:send_market_order(Qty, ticker)
                    send_telegram_message(telApi, telCid, order)
                    return order  # Return the quantity for the order placement
            else:
                send_telegram_message(telApi, telCid, f"{ticker} is not a valid symbol.")
                return f"{ticker} is not a valid symbol."

        elif str.lower(order.command) in ['sellmarket', 'marketsell']:

            if is_valid_symbol(ticker):
                Qty = calculate_trade_quantity(order.risk, str.lower('units'), order.price, ticker)
                if isinstance(Qty, str):
                    send_telegram_message(telApi, telCid, Qty)
                    return Qty  # Return the error message
                else:
                    order = send_market_order_with_tp_sl(-Qty, ticker, order.tp_price, order.sl_price)
                    send_telegram_message(telApi, telCid, order)
                    return order  # Return the quantity for the order placement
            else:
                send_telegram_message(telApi, telCid, f"{ticker} is not a valid symbol.")
                return f"{ticker} is not a valid symbol."

        elif str.lower(order.command) in ['selllimit', 'limitsell']:

            if is_valid_symbol(ticker):
                Qty = calculate_trade_quantity(order.risk, str.lower('units'), order.price, ticker)
                if isinstance(Qty, str):
                    send_telegram_message(telApi, telCid, Qty)
                    return Qty  # Return the error message
                else:
                    order = send_limit_order_with_tp_sl(-Qty, ticker, order.price, order.tp_price, order.sl_price) #:send_market_order(Qty, ticker)
                    send_telegram_message(telApi, telCid, order)
                    return order  # Return the quantity for the order placement
            else:
                send_telegram_message(telApi, telCid, f"{ticker} is not a valid symbol.")
                return f"{ticker} is not a valid symbol."

        elif str.lower(order.command) in ['closebuy', 'buyclose']:

            if is_valid_symbol(ticker) or ticker == None:
                close = close_long_positions(ticker, order.risk)
                send_telegram_message(telApi, telCid, close)
                return close  # Return the error message
            else:
                send_telegram_message(telApi, telCid, f"{ticker} is not a valid symbol.")
                return f"{ticker} is not a valid symbol."

        elif str.lower(order.command) in ['closesell', 'sellclose']:

            if is_valid_symbol(ticker) or ticker == None:
                close = close_short_positions(ticker, order.risk)
                send_telegram_message(telApi, telCid, close)
                return close  # Return the error message
            else:
                send_telegram_message(telApi, telCid, f"{ticker} is not a valid symbol.")
                return f"{ticker} is not a valid symbol."

        elif str.lower(order.command) in ['closeall', 'allclose'] :

            close = close_all_positions()
            send_telegram_message(telApi, telCid, close)
            return close  # Return the error message

        else:
            msg = str(order.command) + " Is Not A Valid Command"
            send_telegram_message(telApi, telCid, msg)
            return msg
    
    else : 
        msg = 'Command Is Empty Or ' + str(order.command)
        send_telegram_message(telApi, telCid, msg)
        return msg






def get_symbol_price(symbol):

    # Construct the AccountDetails request
    # Construct the Pricing request
    params = {"instruments": symbol}
    request = PricingInfo(accountID=account_id, params=params)

    try:
        response = api.request(request)
        prices = response["prices"]
        # Extract the bid price and ask price
        if prices:
            price_info = prices[0]
            bid_price = float(price_info["bids"][0]["price"])
            ask_price = float(price_info["asks"][0]["price"])

            # Calculate the mid price (or use bid/ask based on preference)
            mid_price = (bid_price + ask_price) / 2
            print("Mid is " + str(mid_price))
            return mid_price
            
        else:
            print("No price data available for the instrument.")
            return None
    except V20Error as e:
        print("V20Error occurred:", e)
        prices = None



# Function to get entry price by order ID
def get_entry_price_by_order_id(order_id):
    # r = OrderDetails(accountID=account_id, orderID=order_id)
    r = TradeDetails(accountID=account_id, tradeID=order_id)
    try:
        response = api.request(r)
        print(response)
        if response and 'order' in response:
            entry_price = response['order'].get('price')
            if entry_price:
                return entry_price
            else:
                print('Entry price not found in order details.')
                return None
        else:
            print('Order details not found.')
            return None
    except V20Error as e:
        print(f'Error: {e}')
        return None



# Function to validate the order ID
def validate_order_id(order_id):
    r = OrderDetails(accountID=account_id, orderID=order_id)
    try:
        response = api.request(r)
        if 'order' in response:
            return True
        else:
            print('Order details not found.')
            return False
    except V20Error as e:
        print(f'Error validating order ID: {e}')
        return False
    


def place_sl_tp_order(trade_id, stop_loss_price=None, take_profit_price=None):
    data = {}
    print(stop_loss_price)
    print(take_profit_price)
    # Add takeProfit to data if take_profit_price is provided
    if take_profit_price is not None:
        data["takeProfit"] = {
            "price": str(take_profit_price)
        }

    # Add stopLoss to data if stop_loss_price is provided
    if stop_loss_price is not None:
        data["stopLoss"] = {
            "price": str(stop_loss_price)
        }

    r = TradeCRCDO(accountID=account_id, tradeID=trade_id, data=data)
    try:
        response = api.request(r)
        return response
    except V20Error as e:
        print(f'Error placing SL/TP order: {e}')
        return None










def send_market_order_gap(quantity, symbol, sl_gap=None, tp_gap=None):
    """
    Sends a market order and optionally sets SL and TP orders based on gaps.
    
    Args:
    quantity (int): Number of units to buy/sell.
    symbol (str): Instrument symbol.
    sl_gap (float, optional): Gap for stop loss. Default is None.
    tp_gap (float, optional): Gap for take profit. Default is None.
    
    Returns:
    str: Message with order details or error.
    """
    order_side = "Buy" if quantity > 0 else "Sell"
    dec = decimal(symbol)

    # Order details
    order_data = {
        "order": {
            "type": "MARKET",
            "instrument": symbol,
            "units": quantity  # Specify your position size here
        }
    }

    # Place the order
    order_create_request = OrderCreate(accountID=account_id, data=order_data)
    try:
        response = api.request(order_create_request)

        if 'orderFillTransaction' in response:
            order_fill = response['orderFillTransaction']
            order_id = response['orderCreateTransaction']['id']
            trade_id = order_fill['tradeOpened']['tradeID']
            en_price = float(order_fill['tradeOpened']['price'])
            order_qty = order_fill['units']
            order_symbol = order_fill['instrument']

            msg = f"{order_side} Market Order filled. Order ID: {order_id}/{trade_id}, Instrument: {order_symbol}, Qty: {order_qty}, Price: {en_price}"
            print(msg)

            # Handle SL and TP orders
            if sl_gap is not None or tp_gap is not None:
                tp_prc = round(en_price + tp_gap, dec) if tp_gap is not None else None
                sl_prc = round(en_price - sl_gap, dec) if sl_gap is not None else None
                print(f"TP Price: {tp_prc}, SL Price: {sl_prc}")
                place_sl_tp_order(trade_id, sl_price=str(sl_prc) if sl_prc is not None else None, tp_price=str(tp_prc) if tp_prc is not None else None)

            return msg

        elif 'orderCancelTransaction' in response:
            order_cancel = response['orderCancelTransaction']
            msg = f"{order_side} Market Order Canceled. Order ID: {order_cancel['orderID']}, Reason: {order_cancel['reason']}"
            print(msg)
            return msg
        else:
            msg = "No order fill or cancel transaction found."
            print(msg)
            return msg

    except V20Error as e:
        error_msg = f"Failed to place the market order. Error: {e}"
        print(error_msg)
        return error_msg

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
