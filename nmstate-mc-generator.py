#!/usr/bin/env python

# Copyright 2024 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import copy
import jinja2
import netaddr
from pyramid import config
from pyramid import renderers
from pyramid import response
from pyramid import view
from wsgiref.simple_server import make_server

mc_template = """apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: %(role)s
  name: 10-br-ex-%(role)s
spec:
  config:
    ignition:
      version: 3.2.0
    storage:
      files:
"""

file_template = """      - contents:
          source: data:text/plain;charset=utf-8;base64,%s
        mode: 0644
        overwrite: true
        path: /etc/nmstate/openshift/%s.yml
"""

def gen_output(values):
    mc = ''
    for role in ['master', 'worker']:
        role_count = int(values['%s_count' % role])
        if role_count <= 0:
            continue
        mc += '---<br>'
        mc += mc_template % {'role': role}
        for i in range(role_count):
            hostname = values['%s_hostname_%d' % (role, i)]
            nmstate = values['%s_config_%d' % (role, i)]
            encoded = base64.b64encode(nmstate.encode('utf-8')).decode('utf-8')
            mc += file_template % (encoded, hostname)
    return mc

@view.view_config(route_name='gen')
def gen(request):
    # Remove unset keys so we can use .get() to set defaults
    params = {k: v for k, v in request.params.items() if v}

    loader = jinja2.FileSystemLoader('templates')
    env = jinja2.Environment(loader=loader)
    values = copy.deepcopy(params)
    values['error'] = ''
    do_output = False
    if params.get('generate'):
        do_output = True
        t = env.get_template('output.jinja2')
    else:
        t = env.get_template('gen.jinja2')
    for k, v in values.items():
        if k in params:
            values[k] = params[k]
    try:
        if do_output:
            output = gen_output(values)
            values['output'] = output
        else:
            values['master_count'] = params.get('master_count')
            values['worker_count'] = params.get('worker_count')
            values['masters'] = [i for i in range(int(params.get('master_count', '3')))]
            values['workers'] = [i for i in range(int(params.get('worker_count', '3')))]
    except Exception as e:
        values['error'] = str(e)
    return response.Response(t.render(**values))

if __name__ == '__main__':
    conf = config.Configurator()
    conf.add_route('gen', '/')
    conf.scan()
    app = conf.make_wsgi_app()
    ip = '0.0.0.0' #os.environ['OPENSHIFT_PYTHON_IP']
    port = 8080 #int(os.environ['OPENSHIFT_PYTHON_PORT'])
    server = make_server(ip, port, app)
    server.serve_forever()
