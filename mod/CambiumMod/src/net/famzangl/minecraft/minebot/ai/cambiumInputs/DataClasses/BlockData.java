package net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses;

import java.util.Objects;

public class BlockData {
    double distance;
    int x;
    int y;
    int z;
    boolean solid;
    String name;

    public BlockData(int x, int y, int z, double distance, boolean solid, String name){
        this.x = x;
        this.y = y;
        this.z = z;
        this.solid = solid;
        this.name = name;
        this.distance = distance;
    }

    public int getX(){
        return x;
    }

    public int getY(){
        return y;
    }

    public int getZ(){
        return z;
    }

    public double getDistance(){
        return distance;
    }

    public boolean isSolid(){
        return solid;
    }

    public String getName(){
        return name;
    }

    public String toString(){
        return "X: " + x + " Y: " + y + " Z: " + z + " Solid: " + solid + " Name: " + name;
    }

    @Override
public boolean equals(Object obj) {
    if (this == obj) return true;
    if (obj == null || getClass() != obj.getClass()) return false;
    BlockData that = (BlockData) obj;
    return x == that.x && y == that.y && z == that.z && name.equals(that.name);
}

@Override
public int hashCode() {
    return Objects.hash(x, y, z, name);
}
}
