package net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses;

public class EntityData {

    //Use varibles over Vectors to make API communication simpler
    private boolean isProjectile;
    private boolean isPlayer;
    private double health;
    private double armor;
    private double handDamage;

    private double relativeX;
    private double relativeY;
    private double relativeZ;
    
    private double veloX;
    private double veloY;
    private double veloZ;

    private double facingYaw;
    private double facingPitch;

    public EntityData(boolean isProjectile, boolean isPlayer, double health, double armor, double handDamage, double relativeX, double relativeY, double relativeZ, double veloX, double veloY, double veloZ, double facingYaw, double facingPitch) {
        this.isProjectile = isProjectile;
        this.isPlayer = isPlayer;
        this.health = health;
        this.armor = armor;
        this.handDamage = handDamage;
        this.relativeX = relativeX;
        this.relativeY = relativeY;
        this.relativeZ = relativeZ;
        this.veloX = veloX;
        this.veloY = veloY;
        this.veloZ = veloZ;
        this.facingYaw = facingYaw;
        this.facingPitch = facingPitch;
    }

    public double getHealth() {
        return health;
    }

    public double getArmor() {
        return armor;
    }

    public double getHandDamage() {
        return handDamage;
    }

    public boolean isProjectile(){
        return isProjectile;
    }

    public boolean isPlayer(){
        return isPlayer;
    }

    public double getRelativeX(){
        return relativeX;
    }

    public double getRelativeY(){
        return relativeY;
    }

    public double getRelativeZ(){
        return relativeZ;
    }

    public double getVeloX(){
        return veloX;
    }

    public double getVeloY(){
        return veloY;
    }

    public double getVeloZ(){
        return veloZ;
    }

    public double getFacingYaw(){
        return facingYaw;
    }

    public double getFacingPitch(){
        return facingPitch;
    }

    public String toString(){
        return "Projectile: " + isProjectile + " Player: " + isPlayer + " X: " + relativeX + " Y: " + relativeY + " Z: " + relativeZ + " VeloX: " + veloX + " VeloY: " + veloY + " VeloZ: " + veloZ + " FacingYaw: " + facingYaw + " FacingPitch: " + facingPitch + " Health: " + health + " Armor: " + armor + " HandDamage: " + handDamage;
    }

}
