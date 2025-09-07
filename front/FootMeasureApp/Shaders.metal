#include <metal_stdlib>
using namespace metal;

struct PointVertex {
    float3 position [[attribute(0)]];
    float3 color    [[attribute(1)]];
};

struct Uniforms {
    float4x4 mvp;
    float    pointSize;
};

struct VertexOut {
    float4 position [[position]];
    float4 color;
    float  pointSize [[point_size]];
};

vertex VertexOut vertex_main(const device PointVertex* vertices [[buffer(0)]],
                             constant Uniforms& uniforms        [[buffer(1)]],
                             uint vid                           [[vertex_id]]) {
    VertexOut out;
    float4 pos = float4(vertices[vid].position, 1.0);
    out.position = uniforms.mvp * pos;
    out.color = float4(vertices[vid].color, 1.0);
    out.pointSize = uniforms.pointSize;
    return out;
}

fragment float4 fragment_main(VertexOut in [[stage_in]]) {
    return in.color;
}


