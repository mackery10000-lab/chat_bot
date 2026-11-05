"""Isolated real Flask game fixtures. Never calls a remote model or the player save."""
import json
import os
from pathlib import Path
import sys
import tempfile
from flask import redirect, request
from werkzeug.serving import make_server

BASE = Path(os.environ.get('GAMEPLAY_QA_GAME_ROOT') or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0,str(BASE))
import app as web
from services.chatbot_service import ChatbotService

class LocalModel:
    def interpret(self,message,context):
        if message=='입력창 확인':
            return dict(intent='talk',target=context['active_npc'],topic='off_topic',mode='act',quote=message)
        raise AssertionError('UI checks must not call a live model')
    def generate(self,question,username,character,knowledge):
        return character['_runtime']['canonical']

tmp=tempfile.TemporaryDirectory(prefix='gameplay-ui-qa-')
web.chatbot=ChatbotService(generator=LocalModel(),db_path=Path(tmp.name)/'qa.sqlite3')

@web.app.get('/qa/new')
def seed():
    phase=request.args.get('phase','base')
    gid,state=web.chatbot.store.create('이미지 인벤토리 검수')
    # These fixtures represent progressed saves; new games exercise the real
    # title/name routes in the browser checker, including the opening video.
    state['revision']=1
    state['inventory']=list(web.chatbot.config['items'])
    state['location']='car_3'
    state['flags'].update(light_on=True,elder_features=True,explorer_met=True,
                          supplies_received=True,mission_accepted=True,door_open=True)
    if phase in ('proof','driver','car4','returned','full','control'):
        state['flags'].update(report_found=True,report_read=True,ticket_recovered=True,
                              old_ticket_read=True,ticket_returned=True)
        state['read'].append('route_report')
    if phase in ('proof','driver','control'):
        state['location']='engine'
        state['flags'].update(engine_permission=True,driver_explained=phase in ('proof','control'),year_proven=phase=='control')
    elif phase=='crew': state['location']='crew'
    elif phase in ('car4','door'):
        state['location']='car_4'
        if phase=='door': state['flags']['door_open']=False
    elif phase=='dark': state['flags']['light_on']=False
    elif phase=='full': state['flags']['destination_hint']=True
    elif phase=='early': state['flags']['elder_features']=False
    elif phase=='hint_only':state['flags'].update(elder_features=False,destination_hint=True)
    elif phase=='record_two_actions':
        state['location']='car_4'
        state['flags'].update(report_found=True,report_read=False)
    elif phase=='acquire':
        state.update(location='car_2',npc='explorer',scenario_steps={'explorer':'answer'})
        state['inventory']=['ticket_current']
        state['flags']={'notice_read':True,'explorer_met':True}
    elif phase.startswith('nav_'):
        state['location']='car_1'
        state['flags'].update(notice_read=True,ticket_recovered=True,
                              ticket_returned=True,destination_hint=True,
                              cover_open=True,lever_down=True)
        if phase=='nav_blocked':state['flags']['notice_read']=False
        elif phase=='nav_engine':
            state['location']='car_4'
            state['flags'].update(report_read=True,engine_permission=True)
        elif phase=='nav_crew_locked':
            state['location']='crew'
            state['flags'].update(report_read=True,engine_permission=False)
        elif phase=='nav_conversation':
            state.update(location='car_2',npc='explorer')
    with web.chatbot.store.connect() as db:
        db.execute('UPDATE games SET state=?,revision=? WHERE id=?',
                   (json.dumps(state,ensure_ascii=False),state['revision'],gid))
    response=redirect('/chat')
    response.set_cookie(web.COOKIE,gid,httponly=True,samesite='Lax')
    return response

server=make_server('127.0.0.1',0,web.app,threaded=True)
if __name__ == '__main__':
    print('QA_PORT='+str(server.server_port),flush=True)
    try:server.serve_forever()
    finally:server.server_close();tmp.cleanup()
