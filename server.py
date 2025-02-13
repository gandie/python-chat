'''
Python chat using sockets and TKinter
Copyright (C) 2019  Max Nijenhuis

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''


import socket
import threading
import time
import json
import os


class ChatServer(object):
    '''
    ChatServer is the server backend class used in python-chat
    It keeps all state variables of the server and handles each client in a
    separate thread
    '''

    # these are class variables shared by all instances
    error_text = '\033[31;1m' + '[ERROR] ' + '\033[m'
    failed_login_text = '[SERVER]: Failed login attempt from %s:%s, username: %s'

    def __init__(self, ip='127.0.0.1', port=5000, users_path='users'):
        '''
        populate instance with attributes
        '''

        self.ip = ip
        self.port = port
        self.users_path = users_path

        self.clients = {}
        self.threads = []

        self.cur_users = {}
        self.known_users = {}

    def run(self):
        '''
        Check users file, prepare socket and then run server main loop:
        Accept new connections and spawn handling thread
        '''
        self.check_users()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()

        while True:
            client_socket, client_address = self.server_socket.accept()
            newthread = threading.Thread(
                target=self.client_thread,
                args=(client_socket, client_address,)
            )
            newthread.start()
            self.threads.append(newthread)

    def check_users(self):
        '''
        check for known users in users file. create users file if not found
        '''

        if not os.path.exists(self.users_path) and \
           not os.path.isfile(self.users_path):
            userfile = open(self.users_path, 'w')
            userfile.close()
            return

        with open(self.users_path) as userfile:
            for line in userfile.readlines():
                known_user, known_passwd = line.split(':;', 2)
                self.known_users[known_user] = known_passwd.strip()

    def update_users_file(self):
        '''
        Called when new user logs in
        '''
        with open(self.users_path, 'w') as userfile:
            for user, password in self.known_users.items():
                line = user + ':;' + password
                userfile.write(line + '\n')

    @staticmethod
    def decode_msg(msg):
        msg = msg.decode()
        msg_dict = json.loads(msg)
        usr = msg_dict.get('usr')
        msg = msg_dict.get('msg')
        return usr, msg

    @staticmethod
    def encode_msg(usr, msg):
        msg_dict = {'usr': usr, 'msg': msg}
        print(msg_dict)
        msg = json.dumps(msg_dict).encode()
        return msg

    def client_thread(self, client_socket, client_address):
        '''
        Worker thread handling client connection
        '''
        while True:
            message = client_socket.recv(4096)
            if not message:
                client_socket.close()
                print(
                    '%s Lost connection to %s:%s' %
                    (self.error_text, *client_address)
                )
                break
            user, message = self.decode_msg(message)

            # invalid message
            if not user or not message:
                print(
                    '%s Invalid message from %s:%s' %
                    (self.error_text, *client_address)
                )
                break  # or continue?

            # print to console for debugging
            print(user + ' > ' + message)

            # tell message to clients
            for c_socket in self.clients:
                # ...remember to cut off password. better solution would be
                # to send pw in separate field - not in message
                c_socket.send(self.encode_msg(user, message.split('|')[0]))

            # check fo login / logoff
            if message == 'LOG OFF':
                client_socket.close()
                print(user + ' logged off')
                self.clients.pop(client_socket)
                self.cur_users.pop(user)
                break
            elif 'LOG ON' in message and client_socket not in self.clients:

                logon, given_passwd = message.split('||', 2)

                # check username
                if user in self.cur_users or user == '[SERVER]':
                    client_socket.send(
                        self.encode_msg('[SERVER]', 'Username already taken')
                    )
                    break

                # check for known/unknown user, do pw check on known ones
                if user in self.known_users:

                    required_passwd = self.known_users[user]
                    print('req' + required_passwd)
                    print('giv' + given_passwd)

                    # abort on wrong password
                    if given_passwd != required_passwd:
                        client_socket.send(
                            self.encode_msg('[SERVER]', 'WRONG PASSWORD')
                        )
                        print(self.failed_login_text % (*client_address, user))
                        break
                else:  # unknown user
                    self.known_users[user] = given_passwd
                    self.update_users_file()

                # memorize new user
                self.cur_users[user] = given_passwd

                # tell client everything's fine and send user list
                self.clients[client_socket] = client_address
                print(
                    'Accepted new connection from %s:%s, username: %s' %
                    (*client_address, user)
                )
                client_socket.send(
                    self.encode_msg('[SERVER]', 'Connection accepted')
                )
                for user in self.cur_users:
                    print('userlist sending: ' + user)
                    time.sleep(.1)
                    client_socket.send(
                        self.encode_msg('[userlist]', user)
                    )
        # main loop finished - close socket
        client_socket.close()


if __name__ == '__main__':
    server = ChatServer()
    print('Starting server on %s:%s' % (server.ip, server.port))
    server.run()
