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
    if (mc.thePlayer == null || mc.theWorld == null) {
        return null; // Ensure the player and world exist
    }

    ArrayList<BlockData> blocks = new ArrayList<BlockData>();

    Vec3 playerEyePos = mc.thePlayer.getPositionEyes(1.0F);

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
        Vec3 end = playerEyePos.addVector(direction.xCoord * maxDistance, direction.yCoord * maxDistance, direction.zCoord * maxDistance);

        // Perform ray trace
        MovingObjectPosition result = mc.theWorld.rayTraceBlocks(playerEyePos, end, false, false, false);

        if (result != null && result.typeOfHit == MovingObjectPosition.MovingObjectType.BLOCK) {
            BlockPos hitPos = result.getBlockPos();
            Block hitBlock = mc.theWorld.getBlockState(hitPos).getBlock();
            blocks.add(new BlockData(
              hitPos.getX() - (int) mc.thePlayer.posX,
              hitPos.getY() -  (int) mc.thePlayer.posY,
              hitPos.getZ() - (int) mc.thePlayer.posZ, 
                result.hitVec.distanceTo(playerEyePos),
              true, 
              hitBlock.getLocalizedName()));
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



