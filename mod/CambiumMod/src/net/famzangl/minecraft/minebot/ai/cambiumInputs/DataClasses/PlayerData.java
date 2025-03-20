package net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses;

public class PlayerData {
    double health;
    double playerYaw;
    double playerPitch;
    double playerX;
    double playerY;
    double playerZ;
    double amror;

    public PlayerData(double health, double playerYaw, double playerPitch, double playerX, double playerY, double playerZ, double amror){
        this.health = health;
        this.playerYaw = playerYaw;
        this.playerPitch = playerPitch;
        this.playerX = playerX;
        this.playerY = playerY;
        this.playerZ = playerZ;
        this.amror = amror;
    }

    public double getHealth(){
        return health;
    }

    public double getPlayerYaw(){
        return playerYaw;
    }

    public double getPlayerPitch(){
        return playerPitch;
    }

    public double getPlayerX(){
        return playerX;
    }

    public double getPlayerY(){
        return playerY;
    }

    public double getPlayerZ(){
        return playerZ;
    }

    public double getAmror(){
        return amror;
    }
    
    public String toString(){
        return "Health: " + health + " Yaw: " + playerYaw + " Pitch: " + playerPitch + " X: " + playerX + " Y: " + playerY + " Z: " + playerZ + " Armor: " + amror;
    }
}
