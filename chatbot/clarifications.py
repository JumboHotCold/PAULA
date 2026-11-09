"""Bounded task state only; never answer evidence or arbitrary instructions."""


def validated_pending(value):
    if not isinstance(value,dict) or not isinstance(value.get('query'),str) or not 0<len(value['query'])<=2000:return None
    if value.get('kind') in ('enrollment','navigation') and set(value)=={'kind','query'}:return dict(value)
    if value.get('kind')!='spelling' or set(value) not in ({'kind','query','choices'},{'kind','query','choices','resume'}):return None
    choices=value.get('choices')
    if not isinstance(choices,list) or not 1<=len(choices)<=3 or not all(isinstance(q,str) and 0<len(q)<=500 for q in choices):return None
    result={'kind':'spelling','query':value['query'],'choices':list(dict.fromkeys(choices))}
    if 'resume' in value:
        resume=validated_pending(value['resume'])
        if not resume or resume['kind']=='spelling':return None
        result['resume']=resume
    return result


def spelling_pending(query,choices,resume=None):
    value={'kind':'spelling','query':query,'choices':list(choices)[:3]}
    if resume and resume.get('kind') in ('enrollment','navigation'):value['resume']=resume
    return validated_pending(value)


def pending_from_stored_reply(query,response):
    """Only call for a server-owned persisted reply, never client history."""
    if not isinstance(response,str) or not response.startswith(('Did you mean ','Ang ibig mo bang sabihin ay ')):return None
    from .suggestions import parse_controls
    return spelling_pending(query,parse_controls(response))
