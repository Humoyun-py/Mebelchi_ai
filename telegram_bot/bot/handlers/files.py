import io

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.handlers.common import linked_user
from bot.keyboards import Nav, back_to_menu
from bot.services.api import ApiError, BackendClient
from bot.services.uploads import UploadRejected, check_upload
from bot.utils.errors import api_error_text
from bot.utils.i18n import t

router = Router(name="files")

@router.callback_query(Nav.filter(F.to == "upload"))
async def ask_upload(callback: CallbackQuery, lang: str) -> None:
    await callback.message.answer(t("upload_ask", lang), reply_markup=back_to_menu(lang))
    await callback.answer()


async def _download(message: Message, file_id: str, file_size: int | None, limit_bytes: int) -> bytes:
    if file_size and file_size > limit_bytes:
        raise UploadRejected("too_large")
    tg_file = await message.bot.get_file(file_id)
    buffer = io.BytesIO()
    await message.bot.download_file(tg_file.file_path, destination=buffer)
    return buffer.getvalue()


@router.message(F.document | F.photo)
async def receive_file(message: Message, api: BackendClient, lang: str, max_upload_mb: int) -> None:
    me = await linked_user(api, message.from_user.id)
    if me is None:
        await message.answer(t("not_linked", lang))
        return
    if message.document is not None:
        doc = message.document
        filename, file_id, size = doc.file_name or "document", doc.file_id, doc.file_size
    else:
        photo = message.photo[-1]
        filename, file_id, size = f"photo_{photo.file_unique_id}.jpg", photo.file_id, photo.file_size
    try:
        content = await _download(message, file_id, size, max_upload_mb * 1024 * 1024)
        checked = check_upload(filename, content, max_upload_mb * 1024 * 1024)
        saved = await api.upload_file(message.from_user.id, checked.filename, checked.content)
    except UploadRejected as exc:
        await message.answer(t(f"upload_rejected_{exc.reason}", lang))
        return
    except ApiError as exc:
        await message.answer(api_error_text(exc, lang))
        return
    await message.answer(t("upload_ok", lang, name=saved["name"], percent=saved["storage_percent"]),
                         reply_markup=back_to_menu(lang))
