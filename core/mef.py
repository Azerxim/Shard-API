# Version 1.1

# •••••••••••••••••••••••••••••••••••••••
# Fonction de mise en forme
def MEF(msg, source, destination):
    if type(msg) is dict:
        for k in msg.keys():
            if type(msg[k]) is str:
                msg[k] = msg[k].replace(source, destination)
            else:
                MEF(msg[k], source, destination)
    elif type(msg) is list:
        for x in range(0, len(msg)):
            if type(msg[x]) is str:
                msg[x] = msg[x].replace(source, destination)
            else:
                MEF(msg[x], source, destination)
    elif type(msg) is str:
        msg = msg.replace(source, destination)
    return msg

# •••••••••••••••••••••••••••••••••••••••
def MEFi(text,index=0,replacement=''):
    return '%s%s%s'%(text[:index],replacement,text[index+1:])