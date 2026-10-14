"""Благодарит за каждые чаевые. За золото благодарность побольше.

Событие ``on_tip`` приходит о любых чаевых в комнате, а не только о чаевых боту;
пример ниже благодарит за все. Как отобрать чаевые именно боту — в tipping_bot.py.
"""

from sukarisebot import Bot, CurrencyItem, Item, User


class ThankYou(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if isinstance(item, CurrencyItem):
            await self.api.chat(f"Спасибо, {sender.username}, за {item.amount} золота!")
        else:
            await self.api.chat(f"Спасибо, {sender.username}, за подарок!")


if __name__ == "__main__":
    ThankYou().start()
