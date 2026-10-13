def classFactory(iface):
    from .plugin import ZoneOpasnostiPlugin
    return ZoneOpasnostiPlugin(iface)
