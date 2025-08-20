##Repository config:
On the linux server generate a SSH key :
  ssh-keygen

Add the public key :
  cat cat ~/.ssh/id_ed25519.pub

To the github deploy keys, without write permission.

##Dependencies:
Install the needed packages:
  apt update
  apt upgrade
  apt install git python3 python3-pip
  pip install shyaml --break-system-packages

##Installation:
  cd /opt
  git clone git@github.com:Obinoben/msdl_sync.git

Copy all files in config folder to /etc/quadrumane.
Edit all files to suit your needs.
