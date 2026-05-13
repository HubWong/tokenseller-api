from abc import ABC, abstractmethod
from bip_utils import Bip84,Bip84Coins, Bip39MnemonicGenerator,Bip39WordsNum, Bip39SeedGenerator,Bip44Changes, Bip44, Bip44Coins
from app.core.config import settings
from pathlib import Path
from app.services.tools_svc import set_env_if_not_exists
from dotenv import find_dotenv

env_path = find_dotenv() 

# --------------------------
# 助记词生成
# --------------------------
def generate_mnemonic(strength: int = 256) -> str:
    """
    生成助记词,默认24个单词
    """
    words_num = {
        128: Bip39WordsNum.WORDS_NUM_12,
        160: Bip39WordsNum.WORDS_NUM_15,
        192: Bip39WordsNum.WORDS_NUM_18,
        224: Bip39WordsNum.WORDS_NUM_21,
        256: Bip39WordsNum.WORDS_NUM_24,
    }.get(strength, Bip39WordsNum.WORDS_NUM_24)

    return str(Bip39MnemonicGenerator().FromWordsNumber(words_num))


# --------------------------
# 根据助记词生成种子
# --------------------------
def generate_seed(mnemonic: str, passphrase: str = "") -> bytes:
    return Bip39SeedGenerator(mnemonic).Generate(passphrase)


# --------------------------
# 生成 xprv/xpub
# --------------------------
def gen_xprv_xpub(seed: bytes, coin_type: Bip44Coins) -> dict:
    bip = Bip44.FromSeed(seed, coin_type=coin_type)
    account = bip.Purpose().Coin().Account(0)  # 默认第0号账户
    xprv = account.PrivateKey().ToExtended()
    xpub = account.PublicKey().ToExtended()
    return {
        "xprv": xprv,
        "xpub": xpub
    }


# --------------------------
# 根据 xpub 派生地址
# --------------------------
def derive_addr(xpub: str, index: int, coin: Bip44Coins|Bip84Coins) -> str:
    if coin== Bip84Coins.BITCOIN:
        bip = Bip84.FromExtendedKey(xpub, Bip84Coins.BITCOIN)
        return (
            bip.Change(Bip44Changes.CHAIN_EXT)
            .AddressIndex(index)
            .PublicKey()
            .ToAddress()
        )
        
         
    bip = Bip44.FromExtendedKey(xpub, coin_type=coin)
    addr = bip.Change(Bip44Changes.CHAIN_EXT).AddressIndex(index).PublicKey().ToAddress()
    return addr

 

# --------------------------
# 批量获取主地址
# --------------------------
def get_main_addresses(xpubs: list[dict]) -> dict:
    """
    输入: [{'btc': zpub}, {'eth': xpub}, {'tron': xpub}]
    输出: {'btc': addr, 'eth': addr, 'tron': addr}
    """
    res = {}
    for k in xpubs:
        if 'btc' in k:
            res['btc'] = derive_addr(k['btc'], 0, Bip84Coins.BITCOIN)
        if 'eth' in k:
            res['eth'] = derive_addr(k['eth'], 0, Bip44Coins.ETHEREUM)
        if 'tron' in k:
            res['tron'] = derive_addr(k['tron'], 0, Bip44Coins.TRON)
    return res


# --------------------------
# 写入 .env
# --------------------------
def write_to_env(mnemonic: str, xpubs: dict, path: str = ".env"):
    env_path = Path(path)
    with env_path.open("w") as f:
        f.write(f"MNEMONIC={mnemonic}\n")
        for k, v in xpubs.items():
            f.write(f"{k.upper()}={v}\n")


def gen_btc_account(seed: bytes):
    bip = Bip84.FromSeed(seed, Bip84Coins.BITCOIN)
    account = bip.Purpose().Coin().Account(0)

    return {
        "xprv": account.PrivateKey().ToExtended(),
        "xpub": account.PublicKey().ToExtended()  # 这里其实是 zpub
    }
    
def gen_xpubs_by_monic():
    mnemonic= settings.MNOMNIC
    if not mnemonic:
        mnemonic = generate_mnemonic()
    seed = generate_seed(mnemonic)

    # 生成 xprv/xpub
    btc_keys =  gen_btc_account(seed=seed)
    eth_keys = gen_xprv_xpub(seed, Bip44Coins.ETHEREUM)
    tron_keys = gen_xprv_xpub(seed, Bip44Coins.TRON)

    xpubs = {
        "BTC_XPUB": btc_keys["xpub"],
        "ETH_XPUB": eth_keys["xpub"],
        "TRON_XPUB": tron_keys["xpub"],
    }
    xprvs = {'btc_prv':btc_keys['xprv'],
              'eth_prv':eth_keys['xprv'],
              'tron_prv':tron_keys['xprv']
             }
    
    return mnemonic, xpubs,xprvs

# --------------------------
# 生成完整钱包
# --------------------------
def generate_wallet():   

    mnc,xpubs,xprvs = gen_xpubs_by_monic()
    
    # 获取主地址
    main_addresses = get_main_addresses([
        {"btc": xpubs['BTC_XPUB']},
        {"eth": xpubs['ETH_XPUB']},
        {"tron": xpubs['TRON_XPUB']}
    ])

    return {
        "mnemonic": mnc,
        "xprvs": {
            "btc": xprvs["btc_prv"],
            "eth": xprvs["eth_prv"],
            "tron": xprvs["tron_prv"]
        },
        "xpubs": xpubs,
        "main_addresses": main_addresses
    }


def write_xpub_xprv():
    if not env_path:
        raise Exception(".env file not found")
    mmc_xpub_xprv = generate_wallet()
    if mmc_xpub_xprv:
        mmic = mmc_xpub_xprv['mnemonic']
        xprvs = mmc_xpub_xprv['xprvs']
        xpubs = mmc_xpub_xprv['xpubs']
        main_addrs = mmc_xpub_xprv['main_addresses']
        
        bit =  xpubs['BTC_XPUB']
        eth =xpubs['ETH_XPUB']
        tron = xpubs['TRON_XPUB']
        
        bit_prv = xprvs['btc']
        eth_prv = xprvs['eth']
        tron_prv= xprvs['tron']

        set_env_if_not_exists("mnemonic", mmc_xpub_xprv['mnemonic'])
        set_env_if_not_exists(f"XPRV_bit",bit_prv)
        set_env_if_not_exists(f"XPUB_bit", bit)
        
        set_env_if_not_exists(f"XPRV_eth", eth_prv)
        set_env_if_not_exists(f"XPUB_eth", eth)
        
        set_env_if_not_exists(f"XPRV_tron",tron_prv)
        set_env_if_not_exists(f"XPUB_tron", tron)



class BaseWallet(ABC): 
    
    @abstractmethod
    def derive_address(self, index: int) -> dict:
        pass

    @abstractmethod
    async def check_payment(self, address: str, amount: float) -> dict:
        pass

    @abstractmethod
    async def sweep(self, from_index: int, to_address: str, amount: float) -> str:
        pass

    @abstractmethod
    async def get_balance(self, address: str) -> float:
        pass