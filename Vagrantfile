# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  #Set box
  config.vm.box = "ubuntu/trusty64"

  #Do not check fo updates
  config.vm.box_check_update = false

  #Add private network
  config.vm.network "private_network", type: "dhcp"

  #Redirect ports
  config.vm.network "forwarded_port", guest: 43110, host: 43110
  config.vm.network "forwarded_port", guest: 15441, host: 15441

  #Sync folder using NFS if not windows
  config.vm.synced_folder ".", "/vagrant",
      :nfs => !Vagrant::Util::Platform.windows?

  #Virtal Box settings
  config.vm.provider "virtualbox" do |vb|
    # Don't boot with headless mode
    #vb.gui = true

    # Set VM settings
    vb.customize ["modifyvm", :id, "--memory", "512"]
    vb.customize ["modifyvm", :id, "--cpus", 1]
  end

  #Update system
  config.vm.provision "shell",
      inline: "sudo apt-get update -y && sudo apt-get upgrade -y"

  #Install deps
  config.vm.provision "shell",
      inline: "sudo apt-get install msgpack-python python-gevent python-pip python-dev -y"
  config.vm.provision "shell",
      inline: "sudo pip install -r requirements.txt --upgrade"

end
