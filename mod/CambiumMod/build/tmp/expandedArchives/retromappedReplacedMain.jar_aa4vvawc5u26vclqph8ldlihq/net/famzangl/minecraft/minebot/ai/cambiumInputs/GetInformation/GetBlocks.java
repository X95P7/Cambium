package net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.BlockData;
import net.minecraft.client.Minecraft;
import net.minecraft.util.BlockPos;
import net.minecraft.util.MovingObjectPosition;
import net.minecraft.util.Vec3;
import net.minecraft.block.Block;

public class GetBlocks {
    AIHelper helper;

    public GetBlocks(AIHelper helper){
        this.helper = helper;
    }

    public ArrayList<BlockData> doRaytrace(){
        return findBlocksInSphere(20);
    }
    //90 -> 360 60 -> 45 40 -> 20 30 -> 15 20 ->15 10 -> 15 0-> 15 2(1 + 8 + 18 + 24 * 3) + 24
    //max blocks is 234


    // Find blocks within a spherical radius of the player
private ArrayList<BlockData> findBlocksInSphere(double maxDistance) {
    Minecraft mc = helper.getMinecraft();
    if (mc.field_71439_g == null || mc.field_71441_e == null) {
        return null; // Ensure the player and world exist
    }

    ArrayList<BlockData> blocks = new ArrayList<BlockData>();

    Vec3 playerEyePos = mc.field_71439_g.func_174824_e(1.0F);

    // Iterate over spherical coordinates and add blocks found
    blocks.addAll(getBlockFromVector(360 , -90, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(45 , -60, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(20, -40, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(15, -30, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(15, -20, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(15, -10, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(15, 0, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(360 , 90, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(45 , 60, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(20, 40, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(15, 30, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(15, 20, maxDistance, playerEyePos, mc));
    blocks.addAll(getBlockFromVector(15, 10, maxDistance, playerEyePos, mc));

    // Return unique blocks by using a HashSet to remove duplicates
    Set<BlockData> uniqueBlocks = new HashSet<BlockData>(blocks);
    return new ArrayList<BlockData>(uniqueBlocks);
}

// Ray trace in spherical coordinates (thetaStep, phi, maxDistance)
private ArrayList<BlockData> getBlockFromVector(double thetaStep, double phi, double maxDistance, Vec3 playerEyePos, Minecraft mc){
    double theta = 0;
    ArrayList<BlockData> blocks = new ArrayList<BlockData>();

    while (theta <= 360) {
        // Convert spherical to Cartesian coordinates
        double thetaInRadians = Math.toRadians(theta);
        double x = Math.cos(Math.toRadians(phi)) * Math.cos(thetaInRadians);
        double y = Math.sin(Math.toRadians(phi));
        double z = Math.cos(Math.toRadians(phi)) * Math.sin(thetaInRadians);

        Vec3 direction = new Vec3(x, y, z);
        Vec3 end = playerEyePos.func_72441_c(direction.field_72450_a * maxDistance, direction.field_72448_b * maxDistance, direction.field_72449_c * maxDistance);

        // Perform ray trace
        MovingObjectPosition result = mc.field_71441_e.func_147447_a(playerEyePos, end, false, false, false);

        if (result != null && result.field_72313_a == MovingObjectPosition.MovingObjectType.BLOCK) {
            BlockPos hitPos = result.func_178782_a();
            Block hitBlock = mc.field_71441_e.func_180495_p(hitPos).func_177230_c();
            blocks.add(new BlockData(
              hitPos.func_177958_n() - (int) mc.field_71439_g.field_70165_t,
              hitPos.func_177956_o() -  (int) mc.field_71439_g.field_70163_u,
              hitPos.func_177952_p() - (int) mc.field_71439_g.field_70161_v, 
                result.field_72307_f.func_72438_d(playerEyePos),
              true, 
              hitBlock.func_149732_F()));
        }
        theta += thetaStep;
    }
    //either can be used, dpednig if we want duplicates or not 

    // Collect unique blocks using a HashSet
    //Set<BlockData> uniqueBlocks = new HashSet<BlockData>(blocks);
    //return new ArrayList<BlockData>(uniqueBlocks);

    //no duplicates
    return blocks;
}

    }



