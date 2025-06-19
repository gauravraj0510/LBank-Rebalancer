# Interaction Introduction
## URL
 Please initiate API calls with non-China IP. You can compare the delay of different domain names and choose the one with low delay.
## REST API
`https://www.lbkex.net/`

`https://api.lbkex.com/`

`https://api.lbank.info/`

# Authentication
To protect API communication from unauthorized change, all non-public API calls are required to be signed.

## Request Header Setting
You should put the following parameters in every http requests

`contentType:'application/x-www-form-urlencoded'`

`timestamp`: millisecond of current time (1567833674095). It's strongly recommended that you get it from `/v2/timestamp.do`

`signature_method`: RSA/HmacSHA256.

`echostr`: the param is digit or letter，length is from 30 to 40. You can directly use echostr of SDK, it's safe.

## Signature Process (how to generate the 'sign' parameter)
### 1. Get parameter String(need to be signed): 
Each required parameter of API, exclude sign, add three additional parameters(signature_method, timestamp, echostr) , then we get the parameter string which need to be signed. The parameter string should be ordered according to the parameter name (first compares the first letter of all parameter names, in alphabet order, if you encounter the same first letter, then look at the second letter, and so on). For example, if we use user_info API, the parameter string is like

`string parameters="api_key=c821db84-6fbd-11e4-a9e3-c86000d26d7c&echostr=P3LHfw6tUIYWc8R2VQNy0ilKmdg5pjhbxC7&signature_method=RSA&timestamp=1585119477235"`

### 2. Turn parameters into MD5 digest：
The MD5 digest should be Hex encoded and all letters are uppercase.

`string preparedStr = DigestUtils.md5Hex(parameters).toUpperCase()`

### 3. Signature:
Users could use their secret key to perform a signature operation (Base64 coded) by RSA or HmacSHA256.

## RSA method(signature_method = RSA):

use secret key of your api_key，sign the preparedStr(Base64 encode)，then we get the parameter sign.


## Submit：
After we get the parameter 'sign', put it together with all required parameters of endpoint, then submit as 'application/x-www-form-urlencoded'. As user_info endpoint, we should summit the following parameters:

`api_key=6a8d4f1a-b040-4ac4-9bda-534d71f4cb28`
`sign=e73f3b77895d3df27c79481d878a517edd674e8496ed3051b6e70b6d0b1e47bc`

# Spot Trading Endpoints
## Account information

return example:
```
  {
  "canTrade": true,
  "canWithdraw": true,
  "canDeposit": true,
  "balances": [
    {
      "asset": "BTC",
      "free": "4723846.89208129",
      "locked": "0.00000000"
    },
    {
      "asset": "LTC",
      "free": "4763368.68006011",
      "locked": "0.00000000"
    }
  ]
  }
```
HTTP request
`POST /v2/supplement/user_info_account.do`

request parameters

 Parameter name | Parameter type | Required    | Description |
| -------- | ------- | -------- | ------- |
| sign  | string    | is  | signature of request parameter
api_key    |
| api_key | string     | is  | The api_key applied by the user    |

# Place an order

return example:
```
{
  "order_id":"12074652-d827-4f8d-8f52-92a005c6ce53",
  "symbol": "lbk_usdt",
  "custom_id": "12074652-d827"
}
```
HTTP request
POST `/v2/supplement/create_order.do`

market order
`buy_market`: price must be passed, quoted asset quantity;
`sell_market`: amount must be passed, basic asset quantity;

request parameters

| Parameter name | Parameter type | Required | Description |
| -------- | ------- | -------- | ------- |

| api_key	| String |	is	| the api_key applied by the user |

symbol |	String |	Yes	| Transaction pair eth_btc: Ethereum; zec_btc: Zerocoin

type |	String	| yes	| The type of the order, including buy, sell, buy_market, sell_market, buy_maker, sell_maker, buy_ioc, sell_ioc, buy_fok, sell_fok

price	| String | Reference description	| Order price Buy and sell orders: greater than or equal to 0

amount |	String	| Reference description	| Amount of transactions Sell order and sell order: BTC amount is greater than or equal to 0.001

sign |	String	| is	| signature of request parameter

custom_id	| String | No	| User-defined ID, do not repeat by yourself

window	| Long |	No	| Expiration time of order, milliseconds, automatic cancellation of order after timeout (considering the public network time, it is recommended not to exceed 5s)