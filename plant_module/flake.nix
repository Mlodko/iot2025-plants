# This flake installs and starts a Mosquitto MQTT broker
# and sets up a development environment for python 3.13 with aiomqtt and a language server
# 
# To use it install the nix package manager and navigate to the plant_module directory and run:
# nix develop

{
  description = "This flake installs and starts a Mosquitto MQTT broker";
  
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "https://github.com/numtide/flake-utils/archive/main.tar.gz";
  };
  
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system: 
      let 
        pkgs = nixpkgs.legacyPackages.${system};
      in 
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs.python313Packages; [
            # Python packages here
            aiomqtt
            pip
            setuptools
            wheel
          ] ++ [
            # System packages here
            pkgs.mosquitto
            pkgs.python313
            pkgs.pyright
            pkgs.direnv
          ];
          shellHook = ''
            MOSQUITTO_PORT=1883
            echo "Running automated setup..."
            # Start up mosquitto
              if pgrep -x "mosquitto" > /dev/null; then
                echo "Mosquitto is already running"
              else
                echo "Starting Mosquitto MQTT broker..."
                
                mosquitto -p $MOSQUITTO_PORT -d
                
                sleep 2

                if pgrep -x "mosquitto" > /dev/null; then
                  echo "Mosquitto started successfully on port $MOSQUITTO_PORT"
                  echo "You can test it with: mosquitto_pub -h localhost -t test -m 'Hello World'"
                else
                  echo "Failed to start Mosquitto"
                  echo "Try running manually: mosquitto -p $MOSQUITTO_PORT -v"
                fi
              fi
            
              # Setup direnv
              direnv allow

              # Cleanup
              trap 'echo "Stopping Mosquitto..."; pkill -x mosquitto' EXIT
          '';
        };
      }
    );
}