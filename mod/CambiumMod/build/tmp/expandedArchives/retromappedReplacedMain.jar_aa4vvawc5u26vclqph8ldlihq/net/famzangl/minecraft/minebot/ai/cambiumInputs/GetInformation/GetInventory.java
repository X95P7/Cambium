package net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation;

import java.util.ArrayList;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.InventoryData;
import net.minecraft.client.Minecraft;
import net.minecraft.entity.player.InventoryPlayer;
import net.minecraft.item.ItemStack;
import net.minecraft.item.ItemBlock;
import net.minecraft.item.ItemFishingRod;
import net.minecraft.item.ItemSnowball;
import net.minecraft.item.ItemEgg;
import net.minecraft.item.ItemSword;
import net.minecraft.item.ItemBow;
import net.minecraft.item.Item;

public class GetInventory {

    private Minecraft mc;

    public GetInventory(AIHelper helper){
        mc = helper.getMinecraft();
    }

    public ArrayList<InventoryData> getInventoryData(){
        InventoryPlayer inventory = mc.field_71439_g.field_71071_by;
        ArrayList<InventoryData> inventoryData = new ArrayList<InventoryData>();

        for (int i = 0; i < inventory.field_70462_a.length; i++) {
            ItemStack stack = inventory.field_70462_a[i];
            if (stack != null) {
                Item item = stack.func_77973_b();
                boolean isBlock = item instanceof ItemBlock;
                boolean isProjectile = item instanceof ItemEgg || item instanceof ItemSnowball || item instanceof ItemFishingRod;
                int flair = item instanceof ItemFishingRod ? 1 : 0;
                boolean isWeapon = item instanceof ItemSword;
                ItemSword sword = isWeapon ? (ItemSword) item : null;
                double weaponDamage = isWeapon ? sword.func_150931_i() : 1;
                flair = item instanceof ItemBow ? 1 : 0;



                inventoryData.add(new InventoryData(i, stack.field_77994_a, isBlock, isWeapon ,weaponDamage, isProjectile, flair));
            }
        }
        
        return inventoryData;
    }
}
