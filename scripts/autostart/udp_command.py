#!/usr/bin/env python3

import socket
import os
import json
import datetime
import time
import threading
import select

class RCTOpts(object):
	def __init__(self):
		self._configFile = '&INSTALL_PREFIX/etc/rct_config'
		self.options = ['ping_width_ms',
						'ping_min_snr',
						'ping_max_len_mult',
						'ping_min_len_mult',
						'gps_mode',
						'gps_target',
						'gps_baud',
						'frequencies',
						'autostart',
						'output_dir',
						'sampling_freq',
						'center_freq']
		self._params = {key:self.get_var(key) for key in self.options}

	def get_var(self, var):
		retval = []
		with open(self._configFile) as var_file:
			for line in var_file:
				if line.split('=')[0].strip() == var:
					retval.append(line.split('=')[1].strip().strip('"').strip("'"))
		return retval

	def loadParams(self):
		self._params = {key:self._get_var(key) for key in self.options}

	def getOption(self, option):
		return self._params[option]

	def setOption(self, option, param):
		self._params[option] = param

	def writeOptions(self):
		with open(self._configFile, 'w') as var_file:
			for key, value in list(self._params.items()):
				for val in value:
					opt = '%s=%s\n' % (key, val)
					print(opt)
					var_file.write(opt)


class CommandListener(object):
	"""docstring for CommandListener"""
	def __init__(self, memoryMap, switchOffset):
		super(CommandListener, self).__init__()
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		self.sock.setblocking(0)
		self.port = 9000
		self.target_ip = '255.255.255.255'
		self.ping_file = None
		self.num = None
		self.newRun = False
		self._run = True
		self.sender = threading.Thread(target=self._sender)
		self.receiver = threading.Thread(target=self._listener)
		self.startFlag = False
		self.sharedStates = memoryMap
		self.startOffset = switchOffset
		self.sharedStates[self.startOffset] = False

		self._options = RCTOpts()

		self.sender.start()
		self.receiver.start()

	def __del__(self):
		self._run = False
		self.sender.join()
		self.sock.close()
		if self.ping_file is not None:
			self.ping_file.close()

	def stop(self):
		self._run = False
		self.sender.join()
		self.sharedStates[self.startOffset] = False


	def setRun(self, runDir, runNum):
		self.newRun = True
		if self.ping_file is not None:
			ping_file.close()
		self.ping_file = open(os.path.join(runDir, 'LOCALIZE_%06d' % (runNum)))

	def getStartFlag(self):
		return self.startFlag

	def _sender(self):
		prevTime = datetime.datetime.now()
		sendTarget = (self.target_ip, self.port)

		while self._run:
			try:
				now = datetime.datetime.now()
				if (now - prevTime).total_seconds() > 1:
					heartbeatPacket = {}
					heartbeatPacket['heartbeat'] = {}
					heartbeatPacket['heartbeat']['time'] = time.mktime(now.timetuple())
					heartbeatPacket['heartbeat']['id'] = 'mav'
					msg = json.dumps(heartbeatPacket)
					self.sock.sendto(msg.encode('utf-8'), sendTarget)
					prevTime = now

				if self.ping_file is not None:
					line = ping_file.readline()
					if line == '':
						continue
					if 'stop' in json.loads(line):
						break
					self.sock.sendto(line.encode('utf-8'), sendTarget)
			except Exception as e:
				print("Early Fail!")
				print(e)
				break

	
		return None

	def _gotStartCmd(self, commandPacket, addr):
		self.startFlag = True
		self.sharedStates[self.startOffset] = True
		print("Set start flag")

	def _gotStopCmd(self, commandPacket, addr):
		self.startFlag = False
		self.sharedStates[self.startOffset] = False

	def _gotSetFCmd(self, commandPacket, addr):
		if 'frequencies' not in commandPacket:
			return
		freqs = commandPacket['frequencies']
		self._options.setOption('frequencies', freqs)
		self._options.writeOptions()

	def _gotGetFCmd(self, commandPacket, addr):
		pass

	def _processCommand(self, commandPacket, addr):
		commands = {
			'test': lambda: None,
			'start': self._gotStartCmd,
			'stop': self._gotStopCmd,
			'setF': self._gotSetFCmd,
			'getF': self._gotGetFCmd
		}

		print('Got action: %s' % (commandPacket['action']))

		try:
			commands[commandPacket['action']](commandPacket, addr)
		except Exception as e:
			print(e)

	def _listener(self):

		self.sock.bind(("", self.port))

		while self._run:
			ready = select.select([self.sock], [], [], 1)
			if ready[0]:
				data, addr = self.sock.recvfrom(1024)
				msg = data.decode('utf-8')
				packet = json.loads(msg)
				if 'cmd' in packet:
					print(packet['cmd']['action'])
					self._processCommand(packet['cmd'], addr)