#!/usr/bin/python
DOCUMENTATION = '''
module: vagrant
short_description: vagrant module to init, start, stop, and destroy vagrant systems.
description:  This module is intended to allow for the initialization, starting, stoping, and destroying of vagrant systems.  This motive for this module was to allow for developers to create micro-clouds/datacenters on their local system to aid in prototyping, development, and testing of Ansible playbooks.
options:
  - init
  - up
  - init-up
  - halt
  - destroy
notes:
  This module requires that vagrant and virtualbox (vboxmanage) binaries are in the PATH.
author: Benjamin Harristhal
github: https://github.com/bharristhal/ansible-vagrant-module
''' 
import sys
import subprocess
import re

# /// sys_cmd class ///
class sys_cmd(object):
  
  def __init__(self):
    pass

  def create_dir(self, dir):
    try:
        os.makedirs(dir, 0755)
    except OSError, e:
        pass

  def write_file(self, file, content):
    self.f = open( file, 'w')
    for line in content:
      self.f.write(line)
    self.f.close()

  def execute_cmd( self, cmd ):
    p = subprocess.Popen( cmd, stdout=subprocess.PIPE, shell=True)
    p_stdout = p.communicate()
    return p_stdout

# /// end sys_cmd ///

# /// vagrant control class ///
class vagrantctl(object):

  def __init__( self, sys_cmd ):
    self.sys_cmd = sys_cmd

  def is_name_unique( self, name ):
    cmd = 'vagrant global-status | grep virtualbox | awk \'{print $2}\''
    cmd_output = self.sys_cmd.execute_cmd( cmd )
    if name not in cmd_output[0]:
      return True
    else:
      return False

  """
    Create a system wide unique name
    A unique system name is created by adding a number to the end of
    the system name.
  """
  def create_unique_system_name( self, name ):
    while ( not self.is_name_unique(name) ):
      numbers = "0123456789"
      n = filter( lambda x: x in numbers, name)
      s = filter( lambda x: x not in numbers, name)
      print("Debug: n [{0}]".format( n ))
      if len(n) == 0:
        n+='0'
      int_n = int(''.join(n))
      name = s + str(int_n + 1)
    return name

  def _get_network( self, bridge_pattern ):
    b = None
    cmd_resp = self.sys_cmd.execute_cmd('vboxmanage list bridgedifs | grep ^Name | cut -d\" \" -f2-')
    b = filter( lambda x: bridge_pattern in x, cmd_resp[0].split('\n'))
    # - return the first item in the reduced list.  Don't return the full list.
    return b[0].strip()

  """ Create a vagrant file in the specified locationj"""
  def create_vagrant_file( self, loc, template, uname, **kwargs ):
    self.bridge = None
    if 'bridge' in kwargs:
      self.bridge = kwargs['bridge']
      # ... fetch list of available bridges ...
      self.bridge = self._get_network( self.bridge )
    content = []
    content.append("# -*- mode: ruby -*-\n")
    content.append("# vi: set ft=ruby :\n")
    content.append("Vagrant.configure(2) do |config|\n")
    content.append("config.vm.define '"+ uname + "' do |"+ uname +"|\n")
    content.append( uname + ".vm.box = '" + template + "'\n")
    if ( self.bridge is not None ):
      content.append( uname + ".vm.network \"public_network\", bridge: \"" + self.bridge + "\"\n")
    content.append( "end\n")
    content.append( "end\n")
    self.sys_cmd.create_dir( loc )
    self.sys_cmd.write_file( loc +'/Vagrantfile', content )

  def vagrant_up( self, loc ):
    cmd = "cd "+loc+";vagrant up;"
    output = self.sys_cmd.execute_cmd(cmd)
    json_output = {
      'stdout': output
    }
    return json_output

  def vagrant_info( self, system ):
    # retrieve the global id of the system
    cmd = "vagrant global-status | grep " + system + " | awk \'{print $1}\';"
    (gid,t) = self.sys_cmd.execute_cmd( cmd )
    cmd = "vagrant ssh " + gid.strip('\n') + " -c \"ifconfig\""
    output = self.sys_cmd.execute_cmd( cmd )
    # - - - - Extract IP
    l_output = output[0]
    public_ip=""
    for l in l_output.split('\n'):
        try:
            public_ip = re.search('inet addr:(192.+?)  ', l).group(1)
        except AttributeError:
            pass  # string match not found
    json_output = {
      'gid':gid.strip('\n'),
      'public_ip': public_ip,
      'stdout': output
    }
    return json_output

  def _system_action( self, sys, action ):
        o = []
        resp = self.sys_cmd.execute_cmd('vagrant global-status | grep ' + sys + ' | awk \'{print $1}\'')
        if resp[1] != None:
            # an error is detected
            r = {
              "code":1,
              "msg": resp[1]
            }
            return r
        d = filter( lambda x: len(x)>1, resp[0].split('\n'))
        if len(d) == 0:
            r = {
              "code":0,
              "msg":"No Matching Systems Found."
            }
            return r
        if len( d ) > 1:
            r = {
              "code":1,
              "msg":"Multiple Systems Found. {0}".format(d)
            }
            return r
        cmd = 'vagrant {0} {1}'.format(action, d[0])
        resp = self.sys_cmd.execute_cmd( cmd )
        if resp[1] != None:
            r = {
              "code":1,
              "msg": resp[1]
            }
        else:
            r = {
              "code":0,
              "msg": resp[0]
            }
        return r


  def delete_vagrant_system( self, vsystems ):
      return self._system_action( vsystems, 'destroy -f' )

  def halt_vagrant_system( self, sys_name ):
      return self._system_action( sys_name, 'halt' )

# ///////   End of vagrantctl class /////

def main():
    module = AnsibleModule(
            argument_spec = dict (
                location = dict(),
                template = dict(required=False, default="ubuntu/trusty64"),
                network = dict(),
                name = dict(required=True),
                action = dict(required=True, choices=['init','up','init-up','halt','destroy'])
            )
    )

    vsys = sys_cmd()
    vctl = vagrantctl(vsys)
    json_output = {}

    if module.params.get('action') == 'init' or module.params.get('action') == 'init-up':
        name = vctl.create_unique_system_name( module.params.get('name'))
        location = module.params.get('location') + "/" + name
        vctl.create_vagrant_file( location, module.params.get('template'), name, bridge=module.params.get('network'))
        json_output = {
          'name': name,
          'location': module.params.get('location'),
          'sys_location': location,
          'template': module.params.get('template')
        }

    if module.params.get('action') == 'up' or module.params.get('action') == 'init-up':
        name = vctl.create_unique_system_name( module.params.get('name'))
        location = module.params.get('location') + "/" + name
        o = vctl.vagrant_up( location )
        i = vctl.vagrant_info( name )
        json_output = {
          'vuid':i['gid'],
          'public_ip':i['public_ip'],
          'location' : module.params.get('location'),
          'sys_location': location,
          'template' : module.params.get('template'),
          'name' : name
        }

    if module.params.get('action') == 'halt':
        r = vctl.halt_vagrant_system( module.params.get('name') ) 
        json_output = r

    if module.params.get('action') == 'destroy':
        r = vctl.delete_vagrant_system( module.params.get('name'))
        json_output = r

    module.exit_json(**json_output)

from ansible.module_utils.basic import *
if __name__ == "__main__":
    main()
