import tempfile
from os.path import basename
from zipfile import ZipFile
import configparser
import os

from garnet import ctx
from garnet.runner import RuntimeConfig
from garnet.runner import run
from garnet.filters import text, State, group
from garnet.storages import DictStorage
from garnet.events import Router

router = Router()


class States(group.Group):
    state_waiting = group.M()
    state_uploading = group.M()
    state_naming = group.M()


@router.use()
async def only_pm(handler, event):
    if event.is_private:
        try:
            return await handler(event)
        except Exception as e:
            print("Error happened", e)
            await event.reply(f"An error happened please retry:\nerror code : {e}")
            fsm = ctx.CageCtx.get()  # get UserCage of current user
            await fsm.set_state(States.state_waiting)
            await fsm.set_data({"files": []})


@router.message(text.commands("start", prefixes="/") & (State.exact(States.state_waiting) | State.entry))
async def response(event):
    await event.reply("Hi! Send me a lot of files to zip.\nDo /done to finally zip them and send them back,")
    fsm = ctx.CageCtx.get()  # get UserCage of current user

    await fsm.set_state(States.state_uploading)
    await fsm.set_data({"files": []})


@router.message(State.exact(States.state_waiting) | State.entry)
async def response(event):
    await event.reply("Send /start to start")


@router.message(text.commands("done", prefixes="/") & State.exact(States.state_uploading))
async def finished(event):
    fsm = ctx.CageCtx.get()  # get UserCage of current user
    await fsm.set_state(States.state_naming)
    await event.reply("Please Choose a name for the ZIP file. (no extensions)")


@router.message(State.exact(States.state_naming))
async def naming(event):
    fsm = ctx.CageCtx.get()  # get UserCage of current user
    await fsm.set_state(States.state_waiting)
    data = await fsm.get_data()
    files = data['files']

    msg = await event.reply("Downloading...")
    with tempfile.TemporaryDirectory() as tmp_dirname:
        with ZipFile(f'{tmp_dirname}/{event.text}.zip', 'w') as zipObj2:
            for file in files:
                path = await event.client.download_media(file, file=tmp_dirname)
                zipObj2.write(path, basename(path))
        await msg.edit(f"Finished uploading {len(files)} files. Uploading zip file..")
        await event.reply(file=f'{tmp_dirname}/{event.text}.zip')
    await fsm.set_data({"files": []})


@router.message(State.exact(States.state_uploading))
async def uploading(event):
    if event.file:
        fsm = ctx.CageCtx.get()  # get UserCage of current user
        data = await fsm.get_data()
        files = data['files']
        files.append(event.message.media)
        await fsm.set_data(data)
        await event.reply(f"Saved {len(files)} so far!")

    else:
        await event.reply("Please send a file or /done to finish")


def default_conf_maker() -> RuntimeConfig:
    i = int(os.environ.get("API_ID", 12345))
    a = os.environ.get('API_HASH')
    b = os.environ.get('BOT_TOKEN')
    s = os.environ.get('SESSION_NAME')
    return RuntimeConfig(
        bot_token=b,
        app_id=i,
        app_hash=a,
        session_dsn=s,
    )


async def main():
    main_router = Router().include(router)
    await run(main_router, DictStorage(), conf_maker=default_conf_maker)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
