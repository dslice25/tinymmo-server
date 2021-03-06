import time
import os,ConfigParser
import random
import math
import uuid

from twisted.internet import reactor, task
from twisted.python import log

from player import Player,load_players
from zone import Zone,load_zones
from container import Container
from item import Item
from warp import Warp
from shop import Shop,load_shops
from quest import Quest,load_quests
from loot import Loot,load_loot
from ability import Ability, load_abilities
from playerclass import PlayerClass, load_playerclasses
from accounts import Account, load_accounts

class Game:

  def __init__(self):

    
    # Events queue
    self.events = []

    # Tick counter
    self.tick = time.time()

    # For logging events
    self.last_event = 0
    
    # Warps table
    self.warps = []

    # Items table
    self.items = {}

    # Player spawn location
    self.player_spawn_x = 18
    self.player_spawn_y = 90
    self.player_spawn_zone = 'overworld'

    # Players table
    self.players = {}
    #self.player_index = 0

    #load_players(self, self.player_spawn_x, self.player_spawn_y, self.player_spawn_zone)

    # Monsters table
    self.monsters = {}
    
    # Npcs table
    self.npcs = {}
    
    # Containers table
    self.containers = {}
    self.container_index = 0

    # Zones table
    self.zones = {}
    load_zones(self)

    # Shops table
    self.shops = {}
    load_shops(self)

    # Loot table
    self.loot = {}
    load_loot(self)

    # Quests table
    self.quests = {}
    load_quests(self)

    # Abilities table
    self.abilities = {}
    load_abilities(self)
    
    # Player classes table
    self.playerclasses = {}
    load_playerclasses(self)

    # Accounts Table
    self.accounts = {}
    load_accounts(self)

    # Track buffs/debuffs
    self.active_effects = {}

    # loop task
    self.loop_task = task.LoopingCall(self.loop)
    self.loop_task.start(0.1)

  def process_data(self, player_name, data, protocol=None):
    
    send_now = None
    if data['action'] == 'activate':
      send_now = self.player_activate(player_name, data['ability_name'])
   
    elif data['action'] == 'attack':
      send_now = self.player_attack(player_name)
       
    elif data['action'] == 'equip':
      send_now = self.player_equip(player_name, data['item'])

    elif data['action'] == 'unequip':
      send_now = self.player_unequip(player_name, data['item'])
   
    elif data['action'] == 'buyshopitem':
      send_now = self.buy_shop_item(data['name'], data['item_name'], player_name)

    elif data['action'] == 'sellitem':
      send_now = self.sell_shop_item(player_name, data['item_name'], data['shop_name'])
  
    elif data['action'] == 'drop':
      send_now = self.player_drop(player_name, data['item'])

    elif data['action'] == 'use':
      send_now = self.player_use(player_name, data['item'])
    
    elif data['action'] == 'take':
      send_now = self.player_take(player_name, data['item'])
    
    elif data['action'] == 'acceptquest':
      send_now = self.player_accept_quest(player_name, data['name'])
       
    elif data['action'] == 'settarget':
      send_now = self.set_player_target(player_name, data['target_type'], data['target_name'])
    
    elif data['action'] == 'goto': 
      self.player_goto(player_name, data['x'], data['y'])

    elif data['action'] == 'chat':
      self.chat(player_name, str(data['message']))
    
    elif data['action'] == 'disengage':
      self.player_disengage(player_name)

    elif data['action'] == 'inventory':
      send_now = self.player_inventory(player_name)
   
    elif data['action'] == 'questlog':
      send_now = self.player_questlog(player_name)
    
    elif data['action'] == 'abilities':
      send_now = self.player_abilities(player_name)
     
    elif data['action'] == 'playerstats':
      send_now = self.player_stats(player_name)

    elif data['action'] == 'refresh':
      send_now = self.refresh(player_name)
   
    elif data['action'] == 'getmonster':
      if self.monsters.has_key(data['name']):
        monster = self.monsters[data['name']].state()
        monster['type'] = 'addmonster'
        send_now = {'type': 'events', 'events': [ monster ] }
       
    elif data['action'] == 'getplayer':
      if self.players.has_key(data['name']):
        player = self.players[data['name']].state()
        player['type'] = 'addplayer'
        send_now = {'type': 'events', 'events': [ player ] }
       
    elif data['action'] == 'getnpc':
      if self.npcs.has_key(data['name']):
        npc = self.npcs[data['name']].state()
        npc['type'] = 'addnpc'
        send_now = {'type': 'events', 'events': [ npc ] }

    elif data['action'] == 'getcontainerinv':
      if self.containers.has_key(data['name']):
        if self.containers[data['name']].owner == player_name:
          send_now = self.get_container_inv(data['name'])
    
    elif data['action'] == 'takecontaineritem':
      if self.containers.has_key(data['name']):
        if self.containers[data['name']].owner == player_name:
          send_now = self.take_container_item(data['name'], data['item_name'], player_name)
    
    elif data['action'] == 'getshopinv':
      if self.shops.has_key(data['name']):
        send_now = self.get_shop_inv(data['name'], player_name)
                    
    else:
      print data
       
    return send_now

  def player_stats(self, player_name):

    player = self.players[player_name]
    
    stats = { "title": player.title, "hit": self.get_player_hit(player_name), "dam": self.get_player_dam(player_name), "arm": self.get_player_arm(player_name), "spi": self.get_player_spi(player_name), "hp": player.hp, "mp": player.mp, "gold": player.gold, "exp": player.exp, "level": player.level, "playerclass": player.playerclass.title() }
  
    return { "type": "playerstats", "stats": stats }

  def player_goto(self, player_name, x, y):
    player = self.players[player_name]
    zone = self.zones[player.zone]
    start = player.x,player.y
    end = x,y 
    player.path = zone.get_path(start,end)
    
    #self.events.append({"type": "playerpath", "name": player_name, "path": player.path, "zone": player.zone})

  def refresh(self, player_name):

    zone_name = self.players[player_name].zone
    zone_source = self.zones[zone_name].source

    #zone_data = self.zones[zone_name].client_data
    player_inventory = self.player_inventory(player_name)
    player_stats = self.player_stats(player_name)
    player_quests = self.player_questlog(player_name)
    player_abilities = self.player_abilities(player_name)

    send_now = { 'type': 'refresh', 'player_name': player_name, 'zone_source': zone_source, 'zone': zone_name, 'players': {}, 'monsters': {}, 'npcs': {}, 'containers': {}, 'player_inventory': player_inventory, 'player_stats': player_stats, 'player_quests': player_quests, 'player_abilities': player_abilities }
    #send_now = { 'type': 'refresh', 'player_name': player_name, 'zone_data': zone_data, 'zone': zone_name, 'zone_source': zone_source, 'players': {}, 'monsters': {}, 'npcs': {}, 'containers': {} }
    
    # Add players to send_now dataset
    for k,v in self.players.items():
      if v.zone == zone_name and v.online:
        send_now['players'][k] = v.state()
  
    # Add monsters to send_now dataset
    for k,v in self.monsters.items():
      if v.zone == zone_name:
        send_now['monsters'][k] = v.state()
    
    # Add npcs to send_now dataset
    for k,v in self.npcs.items():
      if v.zone == zone_name:
        send_now['npcs'][k] = v.state()
  
    # Add containers to send_now dataset
    for k,v in self.containers.items():
      if v.zone == zone_name:
        send_now['containers'][k] = v.state()
  
    return send_now


  def get_events(self, player_name, upto):

    # Collect all events from the relevant zone    
    event_list = [ e for e in self.events[upto:] if e['zone'] in [ 'all', self.players[player_name].zone, "player_%s" % player_name ] ]

    return { "type": "events", "events": event_list }

  def create_player(self, title, gender, hairstyle, haircolor, playerclass, account):
    
    items  = self.playerclasses[playerclass].starting_items
    abilities = [ ]
    quests = [ ]
    dam    = 0
    arm    = 0
    hit    = 0
    spi    = 0
    hp     = 10
    mp     = 10
    gold   = 0
    #name   = "player-%s" % self.player_index
    name   = str(uuid.uuid4())
    #name   = "player-%s" % str(uuid.uuid4())[:16]
    #self.player_index += 1
    new_player = Player(name, title, 1, playerclass, 0, gender, 'light', hairstyle, haircolor, 'xxxx', self.player_spawn_x, self.player_spawn_y, self.player_spawn_zone, items, abilities, quests, hp, mp, hit, dam, arm, spi, account, self)
    new_player.online = True
    
    return new_player.name

  def player_join(self, player_name):
    
    # New player data
    self.players[player_name].online = True
      
    # Add addplayer event
    event = { 'type': 'addplayer' }
    event.update(self.players[player_name].state())
    self.events.append(event)

    return player_name

  def cleanup_monster(self, monster):
    # drop monster
    self.events.append({'type': 'dropmonster', 'name': monster.name, 'title': monster.title, 'zone': monster.zone })
    
    # award exp to killer
    monster.target.exp += ( monster.level / monster.target.level ) * ( 10 * monster.level )

    # check if this death satisfies quests
    for quest in monster.target.quests.values():
      quest.check_goal(monster.name)

    # create container object holding monster treasure
    container_name = "container-%s" % self.container_index 
    self.container_index += 1
    title = "Remains of %s" % monster.title
    x = monster.x
    y = monster.y
    zone = monster.zone

    # award random amount of gold 
    gold = random.randint(self.loot[monster.loot].gold_min, self.loot[monster.loot].gold_max)
    
    create_container = False
    # 50% chance of common 
    for i in self.loot[monster.loot].items_common:
      if random.random() < .50:
        item = Item(i, None, container_name, False, self)
   
    # 10% chance of uncommon
    for i in self.loot[monster.loot].items_uncommon:
      if random.random() < .10:
        item = Item(i, None, container_name, False, self)
    
    # 5% chance of rare
    for i in self.loot[monster.loot].items_rare:
      if random.random() < .05:
        item = Item(i, None, container_name, False, self)
    
    self.containers[container_name] = Container(title, container_name, x, y, zone, gold, monster.target.name)
    self.events.append({'type': 'addcontainer', 'name': container_name, 'title': title, 'x': x, 'y': y, 'zone': zone })
    
    # clean up container after 60 sec
    reactor.callLater(60.0, self.cleanup_container, container_name)
    
    # Really delete monster
    monster.spawn.spawn_count -= 1
    del self.monsters[monster.name]


  def cleanup_npc(self, npc):
    # drop npc
    self.events.append({'type': 'dropnpc', 'name': npc.name, 'title': npc.title, 'zone': npc.zone })

    # award exp to killer
    npc.target.exp += ( npc.level / npc.target.level ) * ( 10 * npc.level )

    # create container object holding npc treasure
    #container_name = "container-%s" % self.container_index 
    container_name = str(uuid.uuid4())
    self.container_index += 1
    title = "Remains of %s" % npc.title
    x = npc.x
    y = npc.y
    zone = npc.zone

    # award random amount of gold 
    gold += random.randint(self.loot[npc.loot].gold_min, self.loot[npc.loot].gold_max)
    
    create_container = False
    # 50% chance of common 
    for i in self.loot[npc.loot].items_common:
      if random.random() < 0.5:
        item = Item(i, None, container_name, False, self)
   
    # 10% chance of uncommon
    for i in self.loot[npc.loot].items_uncommon:
      if random.random() < 0.1:
        item = Item(i, None, container_name, False, self)
    
    # 5% chance of rare
    for i in self.loot[npc.loot].items_rare:
      if random.random() < 0.05:
        item = Item(i, None, container_name, False, self)

    self.containers[container_name] = Container(title, container_name, x, y, zone, npc.target.name)
    self.events.append({'type': 'addcontainer', 'name': container_name, 'title': title, 'x': x, 'y': y, 'zone': zone, 'source': source, 'source_w': 32, 'source_h': 32, 'source_x': 0, 'source_y': 0})
    
    # clean up container after 60 sec
    reactor.callLater(60.0, self.cleanup_container, container_name)

    npc.spawn.spawn_count -= 1
    del self.npcs[npc.name]

  def get_shop_inv(self, name, player_name):
    
    player_inv = self.player_inventory(player_name)

    # TODO Filter out stuff player not allowed to sell
    # TODO ONly return if player is in good range of shop

    return { 'type': 'shopinv', 'name': name, 'title': self.shops[name].title, 'inventory': self.shops[name].get_inventory(), 'player_inventory': player_inv['inventory'] }

  def get_container_inv(self, name):
    
    # TODO: Only reutrn if player is in good range of container
     
    inv = {}
    for k,v in self.items.items():
      if v.container == name and v.player == None:
        inv[k] = v.state()
    
    # Add special 'gold' item
    if self.containers[name].gold > 0:
      gold_name = "%s-gold" % name
      inv[gold_name] = { 'title': "%s Gold" % self.containers[name].gold, 
                         'name': gold_name, 
                         'icon': 'coin', 
                         'hit': 0, 
                         'dam': 0, 
                         'arm': 0, 
                         'spi': 0, 
                         'speed': 0, 
                         'value': self.containers[name].gold, 
                         'hp': 0, 
                         'mp': 0, 
                         'consumeable': False }


    return { 'type': 'containerinventory', 'name': name, 'title': self.containers[name].title, 'inventory': inv }

  def take_container_item(self, container_name, item_name, player_name):

    # player is taking gold
    if item_name == "%s-gold" % container_name:
      self.players[player_name].gold += self.containers[container_name].gold
      self.containers[container_name].gold = 0

    if self.items.has_key(item_name):
      if self.items[item_name].container == container_name:
        self.items[item_name].player = player_name
        self.items[item_name].container = None

    return self.get_container_inv(container_name)

  def buy_shop_item(self, shop_name, item_name, player_name):
    
    self.shops[shop_name].buy(item_name, player_name)

    return self.get_shop_inv(shop_name, player_name) 

  def cleanup_container(self, container_name):

    title = self.containers[container_name].title
    zone  = self.containers[container_name].zone

    self.events.append({'type': 'dropcontainer', 'name': container_name, 'title': title, 'zone': zone})
    
    del self.containers[container_name]
     
  def respawn_player(self, player):
    
    self.events.append({ 'type': 'dropplayer', 'name': player.name, 'zone': player.zone })
    
    # Add addplayer event
    event = { 'type': 'addplayer' }
    player.hp[0] = player.hp[1]
    player.mode = 'wait'
    player.x = self.player_spawn_x
    player.y = self.player_spawn_y
    player.destx = self.player_spawn_x
    player.desty = self.player_spawn_y
    player.zone  = self.player_spawn_zone
    event.update(player.state())
    self.events.append(event)
    
    player_refresh = self.refresh(player.name)
    player_refresh['zone'] = "player_%s" % player.name
    self.events.append(player_refresh)

  def monster_die(self, name):

    self.events.append({ 'type': 'monsterdie', 'name': name, 'zone': self.monster[name].zone })
    
  def remove_monster(self, name):
    
    self.events.append({ 'type': 'dropmonster', 'name': name, 'zone': self.monster[name].zone })
    
    self.monsters[name].spawn.spawn_count -= 1
    del self.monsters[name]

  def npc_die(self,name):
    
    self.events.append({ 'type': 'npcdie', 'name': name, 'zone': self.npcs[name].zone })

  def remove_npc(self, name):
    
    self.events.append({ 'type': 'dropnpc', 'name': name, 'zone': self.npcs[name].zone })
    
    self.npcs[name].spawn.spawn_count -= 1
    del self.npcs[name]

  def set_player_target(self, player_name, target_type, target_name):
    
    tgt = None
    tgt_info = { 'type': 'targetinfo', 'tgt_type': 'none' }
    if target_type == 'npc':
      if self.npcs.has_key(target_name):
        tgt = self.npcs[target_name]
        tgt_info['tgt_type'] = 'npc'
        
        if tgt.quest:
          tgt_info['quest'] = tgt.quest
          # Get quest dialog
        
        if tgt.shop:
          tgt_info['shop'] = tgt.shop
          # Get shop inventory
          
    elif target_type == 'player':
      if self.players.has_key(target_name):
        tgt = self.players[target_name]
        tgt_info['tgt_type'] = 'player'
    
    elif target_type == 'monster':
      if self.monsters.has_key(target_name):
        tgt = self.monsters[target_name]
        tgt_info['tgt_type'] = 'monster'
    
    elif target_type == 'container':
      if self.containers.has_key(target_name):
        tgt = self.containers[target_name]
        tgt_info['tgt_type'] = 'container'
        # Get container inventory

    if tgt:
      self.players[player_name].target = tgt
    else:
      self.players[player_name].target = None

    return tgt_info

  def set_player_target2(self, player_name, x, y):
    
    zone = self.players[player_name].zone
    piz = [ p for p in self.players.values() if p.zone == zone and p.name != player_name and p.online ]
    miz = [ m for m in self.monsters.values() if m.zone == zone ]
    niz = [ n for n in self.npcs.values() if n.zone == zone ]
    ciz = [ c for c in self.containers.values() if c.zone == zone ]
    tgt = None
    objtype = None

    # get thing closest to x,y
    all_things = list(piz + miz + niz + ciz)
    all_things_sorted = sorted(all_things, key=lambda z: math.sqrt( ((x-z.x)**2)+((y-z.y)**2) ))
    
    # if nothing found, unset target
    if len(all_things_sorted) < 1:
      self.players[player_name].target = None
      return { 'type': 'unsettarget', }
    else:
      tgt = all_things_sorted[0]
    
    # if too far from mouse, unset target
    if math.sqrt( ((x-tgt.x)**2)+((y-tgt.y)**2) ) > 3:
      self.players[player_name].target = None
      return { 'type': 'unsettarget', }

    if tgt:
      self.players[player_name].target = tgt
      return { 'type': 'settarget', 'name': tgt.name, 'objtype': tgt.__class__.__name__ }
    else:
      self.players[player_name].target = None
      return { 'type': 'unsettarget', }

  def player_leave(self, player_name):
      
    # Add dropplayer event
    self.events.append({ 'type': 'dropplayer', 'name': player_name, 'zone': self.players[player_name].zone })
    self.players[player_name].online = False
    self.players[player_name].target = None
    self.players[player_name].mode = 'wait'

    # Delete all items owned by player
    #self.items = { k: v for k,v in self.items.items() if v.player != player_name }
    
    #del(self.players[player_name])
    
  def walk(self, player_name, direction):
    '''
    Player requests to go north.
    '''
    
    send_event = False
    zone = self.players[player_name].zone
    startx = self.players[player_name].x
    starty = self.players[player_name].y
    endx = self.players[player_name].x
    endy = self.players[player_name].y

    if direction == 'north':
      endy += 1
    elif direction == 'south':
      endy -= 1
    elif direction == 'east':
      endx += 1
    elif direction == 'west':
      endx -= 1

    # If player is free, then perform action
    if self.players[player_name].free():
      if self.zones[zone].open_at(endx,endy):
        self.players[player_name].reset()
        send_event = True

    if send_event:
      self.players[player_name].x = endx
      self.players[player_name].y = endy
      self.players[player_name].mode = 'running'
      self.players[player_name].direction = direction
      self.events.append({ 'type': 'playermove', 'name': player_name, 'zone': zone, 'direction': direction, 'start': (startx,starty), 'end': (endx,endy) })

  def stopwalk(self, player_name):
    self.players[player_name].mode = 'wait'

    
  def warp(self, player, target_warp):
    
    # Drop player
    self.events.append({ 'type': 'dropplayer', 'name': player.name, 'zone': player.zone })
    
    player.x = target_warp.end_x
    player.y = target_warp.end_y
    player.zone = target_warp.end_zone
    player.path = []
    
    # Add addplayer event
    event = { 'type': 'addplayer' }
    event.update(player.state())
    self.events.append(event)

    player_refresh = self.refresh(player.name)
    player_refresh['zone'] = "player_%s" % player.name
    self.events.append(player_refresh)


  def chat(self, player_name, message):
    
    zone = self.players[player_name].zone
    title = self.players[player_name].title
    self.events.append({ 'type': 'playerchat', 'title': title, 'zone':  zone, 'message': message })

  def player_attack(self, player_name):
    player = self.players[player_name]
     
    if player.target:
      if player.target.__class__.__name__ == 'Npc':
        if player.target.villan:
          if self.in_attack_range(player,player.target):
            player.mode = 'fighting'
      elif player.target.__class__.__name__ == 'Monster':
        if self.in_attack_range(player,player.target):
          player.mode = 'fighting'
 
  def player_activate(self, player_name, ability):
    
    if not self.players.has_key(player_name):
      return
    
    if not self.players[player_name].target:
      return
    
    if ability == 'attack':
      self.player_attack(player_name)
      return
  
    if ability not in self.playerclasses[self.players[player_name].playerclass].abilities:
      return

    if self.abilities.has_key(ability):
      return self.abilities[ability].activate(self.players[player_name], self.players[player_name].target)

  def player_accept_quest(self, player_name, quest_name):
 
    send_now = {}
     
    if not self.quests.has_key(quest_name):
      return send_now

    return self.quests[quest_name].assign(player_name)


  def player_questlog(self, player_name):

    quests = []
    for quest in self.players[player_name].quests.values():
      quests.append(quest.get_log_entry())

    return { 'type': 'questlog', 'quests': quests } 

  def player_buy(self, player_name, item_name):

    shop = self.players[player_name].target.shop
    
    if not self.shops.has_key(shop):
      return

    if len([ i for i in self.items.values() if i.player == player_name ]) >= 12:
      return { 'type': 'message', 'message': "You can't carry any more!" }
  
    self.shops[shop].buy(item_name, player_name)

    return { 'type': 'message', 'message': "You bought a %s" % item_name }

  def player_take(self, player_name, item_name):

    if not self.items.has_key(item_name):
      return

    if not self.items[item_name].container:
      return

    container_name = self.items[item_name].container
    
    if not self.containers.has_key(container_name):
      return

    if not self.containers[container_name].owner == player_name:
      return

    if self.items[item_name].player:
      return
    
    # reassign to player
    self.items[item_name].container = None
    self.items[item_name].player = player_name

    return { 'type': 'message', 'message': "You took the %s" % self.items[item_name].title }

  def sell_shop_item(self, player_name, item_name, shop_name):
    
    if self.shops.has_key(shop_name):
      self.shops[shop_name].sell(item_name, player_name)
   
    return self.get_shop_inv(shop_name, player_name) 
  
  def player_use(self, player_name, item_name):
    # Skip if this item doesn't exist
    if not self.items.has_key(item_name):
      return { 'type': 'message', 'message': 'You cannot use that item.' }
    
    # Skip if this item isn't owned by player
    if self.items[item_name].player != player_name:
      return { 'type': 'message', 'message': 'You cannot use that item.' }

    # Skip if item cannot be consumed 
    if not self.items[item_name].consumeable:
      return { 'type': 'message', 'message': 'You cannot use that item.' }
    
    # Apply HP or MP restores
    if self.items[item_name].hp > 0:
      self.players[player_name].heal(self.items[item_name].hp) 
    
    if self.items[item_name].mp > 0:
      self.players[player_name].restore(self.items[item_name].mp) 
    
    del self.items[item_name]
    
    return self.player_inventory(player_name)

  def player_drop(self, player_name, item_name):
    
    # Skip if this item doesn't exist
    if not self.items.has_key(item_name):
      return { 'type': 'message', 'message': 'You cannot drop that item.' }
    
    # Skip if this item isn't owned by player
    if self.items[item_name].player != player_name:
      return { 'type': 'message', 'message': 'You cannot drop that item.' }
    
    # Skip if this item is already equipped
    if self.items[item_name].equipped:
      return { 'type': 'message', 'message': 'You cannot drop that item.' }
  
    item_title = self.items[item_name].title
    del self.items[item_name]

    return self.player_inventory(player_name)
    
  def player_equip(self, player_name, item_name):
    
    # Skip if this item doesn't exist
    if not self.items.has_key(item_name):
      return { 'type': 'message', 'message': 'You cannot equip that item.' }
    
    # Skip if this item cannot be equipped
    if self.items[item_name].slot == None:
      return { 'type': 'message', 'message': 'You cannot equip that item.' }
    
    # Skip if this item is already equipped
    if self.items[item_name].equipped:
      return
   
    # Skip if this items isn't owned by player
    if self.items[item_name].player != player_name:
      return { 'type': 'message', 'message': 'You cannot equip that item.' }

    # Is there something already in that slot
    slot = self.items[item_name].slot
    if [ i for i in self.items.values() if i.player == player_name and i.slot == slot and i.equipped ]:
      return { 'type': 'message', 'message': 'You already have something equipped there.' }

    self.items[item_name].equipped = True
    gear_type = self.items[item_name].gear_type
    zone = self.players[player_name].zone
    
    if slot == 'armor':
      self.events.append({ 'type': 'setplayerarmor', 'name': player_name, 'zone':  zone, 'armor': gear_type,})
    elif slot == 'weapon':
      self.events.append({ 'type': 'setplayerweapon', 'name': player_name, 'zone':  zone, 'weapon': gear_type,})
    elif slot == 'head':
      self.events.append({ 'type': 'setplayerhead', 'name': player_name, 'zone':  zone, 'head': gear_type,})

    return self.player_inventory(player_name)
    
  def player_unequip(self, player_name, item_name):

    # Skip if this item doesn't exist
    if not self.items.has_key(item_name):
      return { 'type': 'message', 'message': 'You cannot unequip that item.' }
    
    # Skip if this item cannot be equipped
    if self.items[item_name].slot == 'none':
      return { 'type': 'message', 'message': 'You cannot unequip that item.' }
    
    # Skip if this item is unequipped
    if not self.items[item_name].equipped:
      return { 'type': 'message', 'message': 'You cannot unequip that item.' }

    # Skip if this items isn't owned by player
    if self.items[item_name].player != player_name:
      return { 'type': 'message', 'message': 'You cannot unequip that item.' }

    self.items[item_name].equipped = False
    
    slot = self.items[item_name].slot
    zone = self.players[player_name].zone

    if slot == 'armor':
      self.events.append({ 'type': 'setplayerarmor', 'name': player_name, 'zone':  zone, 'armor': 'clothes',})
    elif slot == 'weapon':
      self.events.append({ 'type': 'setplayerweapon', 'name': player_name, 'zone':  zone, 'weapon': 'unarmed',})
    elif slot == 'head':
      self.events.append({ 'type': 'setplayerhead', 'name': player_name, 'zone':  zone, 'head': 'none',})
    
    return self.player_inventory(player_name)

  def player_inventory(self, player_name):
    
    # Return hash of player's items
    inv = {}
    for k,v in self.items.items():
      if v.player == player_name:
        inv[k] = v.state()
    
    return { 'type': 'inventory', 'inventory': inv }

  def player_abilities(self, player_name):
    
    # Return hash of player's abilities
   
    # Player can alway attack
    abil = {}
    abil['attack'] = { 'name': 'attack', 'title': 'Attack', 'icon': 'sword', 'description': 'Engage in combat' }
    
    for a in self.playerclasses[self.players[player_name].playerclass].abilities:
      if self.abilities[a].level <= self.players[player_name].level:
        abil[a] = self.abilities[a].stats()

    return { 'type': 'abilities', 'abilities': abil }

  def player_disengage(self, player_name):
    
    # Player disengages and stops fighting
    self.players[player_name].fighting = False
      
  def get_player_dam(self, player_name):
    '''
    Get total damage of player
    '''
    base_damage = self.players[player_name].dam
    class_damage = self.playerclasses[self.players[player_name].playerclass].dam_bonus
    
    gear_damage = 0
    effect_damage = 0
    
    for item_name,item in self.items.items():
      if item.equipped and item.player == player_name:
        gear_damage += item.dam
    
    for effect_name,effect in self.players[player_name].active_effects.items():
      effect_damage += effect['dam']

    return base_damage + gear_damage + effect_damage + class_damage

  
  def get_player_hit(self, player_name):
    '''
    Get hit bonus for player
    '''
    base_hit = self.players[player_name].hit
    class_hit = self.playerclasses[self.players[player_name].playerclass].hit_bonus
   
    gear_hit = 0
    effect_hit = 0

    for item_name,item in self.items.items():
      if item.equipped and item.player == player_name:
        gear_hit =+ item.hit
    
    for effect_name,effect in self.players[player_name].active_effects.items():
      effect_hit += effect['hit']

    return base_hit + gear_hit + effect_hit + class_hit


  def get_player_arm(self, player_name):
    '''
    Get armor class of player
    '''
    base_arm = self.players[player_name].arm
    class_arm = self.playerclasses[self.players[player_name].playerclass].arm_bonus
    
    gear_arm = 0
    effect_arm = 0
     
    for item_name,item in self.items.items():
      if item.equipped and item.player == player_name:
        gear_arm += item.arm
   
    for effect_name,effect in self.players[player_name].active_effects.items():
      effect_arm += effect['arm']

    return base_arm + gear_arm + effect_arm + class_arm

  def get_player_spi(self, player_name):
    '''
    Get spirit of player
    '''
    base_spi = self.players[player_name].spi
    class_spi = self.playerclasses[self.players[player_name].playerclass].spi_bonus
    
    gear_spi = 0
    effect_spi = 0
    
    for item_name,item in self.items.items():
      if item.equipped and item.player == player_name:
        gear_spi += item.spi
    
    for effect_name,effect in self.players[player_name].active_effects.items():
      effect_spi += effect['spi']

    return base_spi + gear_spi + effect_spi + class_spi

  def get_monster_spi(self, monster_name):
    '''
    Get monster spirit after effects
    '''
    base_spi = self.monsters[monster_name].spi
    effect_spi = 0

    for effect_name,effect in self.monsters[monster_name].active_effects.items():
      effect_spi += effect['spi']

    return base_spi + effect_spi
    
  def get_monster_dam(self, monster_name):
    '''
    Get monster damrit after effects
    '''
    base_dam = self.monsters[monster_name].dam
    effect_dam = 0

    for effect_name,effect in self.monsters[monster_name].active_effects.items():
      effect_dam += effect['dam']

    return base_dam + effect_dam
    
  def get_monster_arm(self, monster_name):
    '''
    Get monster armrit after effects
    '''
    base_arm = self.monsters[monster_name].arm
    effect_arm = 0

    for effect_name,effect in self.monsters[monster_name].active_effects.items():
      effect_arm += effect['arm']

    return base_arm + effect_arm
    
  def get_monster_hit(self, monster_name):
    '''
    Get monster hitrit after effects
    '''
    base_hit = self.monsters[monster_name].hit
    effect_hit = 0

    for effect_name,effect in self.monsters[monster_name].active_effects.items():
      effect_hit += effect['hit']

    return base_hit + effect_hit
    
  def get_npc_spi(self, npc_name):
    '''
    Get npc spirit after effects
    '''
    base_spi = self.npcs[npc_name].spi
    effect_spi = 0

    for effect_name,effect in self.npcs[npc_name].active_effects.items():
      effect_spi += effect['spi']

    return base_spi + effect_spi
    
  def get_npc_arm(self, npc_name):
    '''
    Get npc spirit after effects
    '''
    base_arm = self.npcs[npc_name].arm
    effect_arm = 0

    for effect_name,effect in self.npcs[npc_name].active_effects.items():
      effect_arm += effect['arm']

    return base_arm + effect_arm
    
  def get_npc_dam(self, npc_name):
    '''
    Get npc spirit after effects
    '''
    base_dam = self.npcs[npc_name].dam
    effect_dam = 0

    for effect_name,effect in self.npcs[npc_name].active_effects.items():
      effect_dam += effect['dam']

    return base_dam + effect_dam
    
  def get_npc_hit(self, npc_name):
    '''
    Get npc spirit after effects
    '''
    base_hit = self.npcs[npc_name].hit
    effect_hit = 0

    for effect_name,effect in self.npcs[npc_name].active_effects.items():
      effect_hit += effect['hit']

    return base_hit + effect_hit
    
  def get_player_attack_type(self, player_name):
    
    attack_type = 'slash'
    
    for item_name,item in self.items.items():
      if item.equipped and item.slot == 'weapon' and item.player == player_name:
        if item.gear_type in [ 'sword', 'wand', 'dagger', 'sword', 'rapier', 'saber', 'mace' ]:
          attack_type = 'slash'
        elif item.gear_type in [ 'bow', 'greatbow', 'recurvebow' ]:
          attack_type = 'bow'
        elif item.gear_type in [ 'staff', 'spear', 'trident' ]:
          attack_type = 'thrust'
    
    return attack_type
  
  def get_player_attack_speed(self, player_name):
    
    attack_speed = 3.0
    
    for item_name,item in self.items.items():
      if item.equipped and item.slot == 'weapon' and item.player == player_name:
        attack_speed = item.speed

    return attack_speed

  def get_distance_between(self, obj1, obj2):
    
    return abs(obj1.x - obj2.x) + abs(obj1.y - obj2.y)

  def in_attack_range(self, attacker, target):
    
    distance = self.get_distance_between(attacker,target)
    if attacker.__class__.__name__ == 'Player':
      attack_type = self.get_player_attack_type(attacker.name)
      if attack_type == 'slash':
        if distance < 2:
          return True
      elif attack_type == 'bow':
        if distance < 10:
          return True   
      elif attack_type == 'thrust':
        if distance < 5:
          return True

    elif attacker.__class__.__name__ == 'Npc':
      attack_type = attacker.attack_type
      if attack_type == 'slash':
        if distance < 2:
          return True
      elif attack_type == 'bow':
        if distance < 10:
          return True   
      elif attack_type == 'thrust':
        if distance < 5:
          return True
      
    elif attacker.__class__.__name__ == 'Monster':
      # TODO: Give individual monsters an attack range
      if distance < 2:
        return True

    return False

  def facetarget(self, attacker, target):
    
    new_dir = 'south'

    if target.x > attacker.x:
      new_dir = 'east'
    elif target.x < attacker.x:
      new_dir = 'west'
    elif target.y > attacker.y:
      new_dir = 'north'
    
    if attacker.__class__.__name__ == 'Player':
      self.players[attacker.name].direction = new_dir
      self.events.append({'type': "playerface", 'direction': new_dir, 'zone': attacker.zone, 'name': attacker.name })
    elif attacker.__class__.__name__ == 'Monster':
      self.monsters[attacker.name].direction = new_dir
      self.events.append({'type': "monsterface", 'direction': new_dir, 'zone': attacker.zone, 'name': attacker.name })
    elif attacker.__class__.__name__ == 'Npc':
      self.npcs[attacker.name].direction = new_dir
      self.events.append({'type': "npcface", 'direction': new_dir, 'zone': attacker.zone, 'name': attacker.name })

  def attack(self, attacker, target):
    
    attacker.ready_to_attack = False
    
    hitroll  = 0
    damage = 0
    attack_type = 'attack'
    armor = 0
    attack_speed = 0

    self.facetarget(attacker,target)

    # Gather attacker stats 
    if attacker.__class__.__name__ == 'Player':
      hitroll = random.randint(1,20) + self.get_player_hit(attacker.name)
      damage = random.randint(1, self.get_player_dam(attacker.name) + 1)
      attack_type = 'player'+self.get_player_attack_type(attacker.name)
      attack_speed = self.get_player_attack_speed(attacker.name)
      
    elif attacker.__class__.__name__ == 'Monster':
      hitroll  = random.randint(1,20) + self.get_monster_hit(attacker.name)
      damage = random.randint(1, self.get_monster_dam(attacker.name) + 1)
      attack_type = 'monsterattack'
      attack_speed = attacker.attack_speed
    
    elif attacker.__class__.__name__ == 'Npc':
      hitroll  = random.randint(1,20) + self.get_npc_hit(attacker.name)
      damage = random.randint(1, self.get_npc_dam(attacker.name) + 1)
      attack_type = 'npc'+attacker.attack_type
      attack_speed = attacker.attack_speed
    
    # Gather Target stats 
    if target.__class__.__name__ == 'Npc':
      armor = self.get_npc_arm(target.name)
    elif target.__class__.__name__ == 'Monster':
      armor = self.get_monster_arm(target.name)
    elif target.__class__.__name__ == 'Player':
      armor = self.get_player_arm(target.name)
    
    #print "====%s vs %s====" % (attacker.__class__.__name__,target.__class__.__name__) 
    #print "%s attacks %s with %s:" % (attacker.title,target.title,attack_type)
    #print " %s rolls %s" % (attacker.title,hitroll)
    #print " %s armor is %s" % (target.title, armor + 10)
    
    if hitroll >= armor + 10:
      #print " %s >= %s, it's a hit!" % (hitroll, armor + 10)
      #print " %s takes %s damage" % (target.title,damage)
      
      self.events.append({'type': attack_type, 'hit': True, 'name': attacker.name, 'target': target.name, 'zone': attacker.zone })
      target.take_damage(attacker, damage)

    else:
      print " %s < %s, it's a miss!" % (hitroll, armor + 10)
      
      self.events.append({'type': attack_type, 'hit': False, 'name': attacker.name, 'target': target.name, 'zone': attacker.zone,})
    
    reactor.callLater(attack_speed, attacker.reset_attack)

  def loop(self):
    
    # update game world
    # Keepalive tick
    #if time.time() - 60 > self.tick:
    #  self.events.append({ 'type': 'tick', 'time': time.time(), 'zone': 'all' })
    #  self.tick = time.time()
    
    # Follow event queue
    for e in self.events[self.last_event:]:
      #if e['type'] in ['playermove','npcmove','monstermove']:
      #  continue
      #log.msg( "EVENT %s: %s" % (e['type'], e) )
      pass

    self.last_event = len(self.events)

