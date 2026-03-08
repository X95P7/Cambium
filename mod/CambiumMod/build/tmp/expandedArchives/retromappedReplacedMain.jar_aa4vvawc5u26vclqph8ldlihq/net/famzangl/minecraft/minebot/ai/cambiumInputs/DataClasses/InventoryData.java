package net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses;

//Maps 1 inventory slot

/**
 * Invetory repersentation
 * 9  10 11 12 13 14 15 16 17
 * 18 19 20 21 22 23 24 25 26
 * 27 28 29 30 31 32 33 34 35
 * 0  1  2  3  4  5  6  7  8
 */

public class InventoryData {
    private int slotNumber;
    private int count;
    private boolean isBlock;
    private boolean isWeapon;
    private double weaponDamage;
    private boolean isProjectile;
    private int flair;


    //Generic constructor
    public InventoryData(int slotNumber, int count, boolean isBlock, boolean isWeapon, double weaponDamage, boolean isProjectile, int flair){
        this.slotNumber = slotNumber;
        this.count = count;
        this.isBlock = isBlock;
        this.isWeapon = isWeapon;
        this.weaponDamage = weaponDamage;
        this.isProjectile = isProjectile;
        this.flair = flair;
    }

    //Others can be added as they come (food, buckets, etc)
    public int getSlotNumber(){
        return slotNumber;
    }

    public int getCount(){
        return count;
    }

    public boolean isBlock(){
        return isBlock;
    }

    public boolean isWeapon(){
        return isWeapon;
    }

    public double getWeaponDamage(){
        return weaponDamage;
    }

    public boolean isProjectile(){
        return isProjectile;
    }

    public int getFlair(){
        return flair;
    }

    public String toString(){
        return "Slot: " + slotNumber + " Count: " + count + " isBlock: " + isBlock + " isWeapon: " + isWeapon + " weaponDamage: " + weaponDamage + " isProjectile: " + isProjectile + " flair: " + flair;
    }
}
