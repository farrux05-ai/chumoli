"""
uzpipe.security.crypto
========================

Credentials'ni SQLite'ga yozishdan oldin shifrlash uchun eng minimal,
eng ishonchli qatlam.

NEGA BU MODUL ALOHIDA, "STORE" ICHIGA YOZILMAGAN
----------------------------------------------------
Xavfsizlik kodi qolgan business logikadan har doim ANIQ ajratilishi
kerak — bu narsa "qayerda buzilishi mumkinligini" tekshirishni
osonlashtiradi. Agar kimdir kodni auditdan o'tkazsa, "credentials
qanday shifrlanadi" degan savolga javob berish uchun FAQAT shu bitta
faylni o'qish kifoya qilishi kerak.

NEGA Fernet (symmetric), NEGA ASYMMETRIC EMAS
------------------------------------------------
Bu single-user, local-first ilova (pip install, localhost). Shifrlovchi
va parolni o'quvchi — bir xil mashina, bir xil foydalanuvchi. Asymmetric
kriptografiya (masalan RSA) bu yerda ortiqcha murakkablik qo'shadi va
hech qanday qo'shimcha xavfsizlik bermaydi — chunki private key baribir
shu mashinada saqlanishi kerak bo'lardi. Fernet (AES-128-CBC + HMAC,
`cryptography` kutubxonasining tayyor, tekshirilgan implementatsiyasi)
aynan shu holat uchun mo'ljallangan: "buni faylga saqlayman, keyin
o'zim o'qiyman" degan holat.

NEGA KEY FAYLDA, ENV VARIABLE'DA EMAS
------------------------------------------
Loyihaning "zero friction" tamoyiliga ko'ra, foydalanuvchi hech qanday
qo'shimcha sozlash (masalan ENV VARIABLE qo'yish) qilmasligi kerak.
Key birinchi ishga tushirishda avtomatik generatsiya qilinadi va
foydalanuvchi papkasida saqlanadi (~/.uzpipe/master.key). Bu "npm"
yoki "git" kabi ko'plab CLI tool'lar ishlatadigan naqsh — masalan SSH
key'lar ham xuddi shunday ~/.ssh papkasida turadi.

MUHIM CHEKLOV (ATAYLAB HUJJATLASHTIRILGAN)
-----------------------------------------------
Bu yondashuv "kimdir sizning noutbukingizga jismoniy kirsa yoki fayl
tizimingizni o'qiy olsa" degan tahdidga qarshi HIMOYA QILMAYDI — agar
kimdir ~/.uzpipe/master.key va SQLite faylining ikkalasiga ham kira
olsa, ular parollarni ochishlari mumkin. Bu OS darajasidagi fayl
ruxsatlariga (chmod 600) tayanadi, alohida HSM yoki keychain
integratsiyasi emas. Bu MVP uchun to'g'ri kelishuv: haqiqiy tahdid
modeli — "SQLite fayli tasodifan git'ga commit qilinishi" yoki
"boshqa dastur uni o'qib qo'yishi", bularning ikkalasidan ham bu
yondashuv himoya qiladi.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipher:
    """Bitta master key atrofida yupqa wrapper.

    Bu klass ATAYLAB juda kichik — shifrlash/deshifrlash mantig'ini
    o'zi qayta ixtiro qilmaydi, faqat Fernet'ni to'g'ri key bilan
    ishlatishni ta'minlaydi va key hayot siklini boshqaradi.
    """

    def __init__(self, key_path: Path | None = None) -> None:
        self._key_path = key_path or self._default_key_path()
        self._fernet = Fernet(self._load_or_create_key())

    @staticmethod
    def _default_key_path() -> Path:
        import os
        home = Path(os.environ.get("UZPIPE_HOME") or (Path.home() / ".uzpipe"))
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
        return home / "master.key"

    def _load_or_create_key(self) -> bytes:
        if self._key_path.exists():
            return self._key_path.read_bytes()

        # Yangi key generatsiya qilamiz va DARHOL 600 (faqat egasi
        # o'qiy/yoza oladi) ruxsati bilan yozamiz. Ruxsatni yozishdan
        # KEYIN emas, OLDIN cheklab bo'lmaydi (fayl hali yo'q), shuning
        # uchun yozilgach darhol chmod qilinadi — bu orada boshqa
        # jarayon o'qib olish ehtimoli nazariy jihatdan bor, lekin
        # local-first, single-user ilova uchun bu qabul qilinadigan xavf.
        new_key = Fernet.generate_key()
        self._key_path.write_bytes(new_key)
        os.chmod(self._key_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        return new_key

    def encrypt(self, plaintext: str) -> str:
        """Matnni shifrlab, saqlash uchun tayyor string qaytaradi."""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Shifrlangan stringni asl matnga qaytaradi.

        `InvalidToken` ni ataylab qayta ko'tarmaymiz (o'zgartirmaymiz) —
        chaqiruvchi kod buni to'g'ridan-to'g'ri ushlab, foydalanuvchiga
        "credentials fayli buzilgan yoki master key almashtirilgan"
        degan aniq xabar ko'rsatishi kerak, umumiy Exception emas.
        """
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken:
            raise

    def encrypt_dict(self, values: dict[str, str]) -> dict[str, str]:
        """Bir nechta maxfiy qiymatni birma-bir shifrlaydi.

        control_store bu metodni ConnectorManifest.secret_keys() bilan
        birga ishlatadi: faqat manifest "secret=True" deb belgilagan
        kalitlar shu funksiyaga uzatiladi, qolganlari oddiy JSON
        sifatida saqlanadi.
        """
        return {k: self.encrypt(v) for k, v in values.items()}

    def decrypt_dict(self, values: dict[str, str]) -> dict[str, str]:
        return {k: self.decrypt(v) for k, v in values.items()}
