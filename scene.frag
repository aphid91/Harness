#version 150
uniform int frame_count;
#define ZERO (min(frame_count,0)) // non-constant zero
uniform vec2 resolution;

uniform vec2 mouse;
uniform float time;

#define MAX_STEPS 400
#define MAX_SHADOW_STEPS 230
#define HIT_DISTANCE (1e-4*(r.extent))
#define NORM_DIST 1e-4
#define MAX_DISTANCE 600
#define SMALL_BUMP (HIT_DISTANCE*6.0)

#define FOCAL_LENGTH 1.05
#define pmouse mix(vec2(mouse.x,mouse.y),vec2(.3379+.05,.8288),vec2(0))
#define CAMPOS (dials4.xyz*15+3*vec3(13.1*sin(pmouse.x*3.141*2),30.*pmouse.y-15,-13.1*cos(pmouse.x*3.1415*2)))
#define CAMTAR (dials4.xyz*15+vec3(0))
#define SUN_DIR -axis//normalize(transpose(worldRot)*(-axis-0.21*vec3(3.1,.1,2)))//(-axis)


#define SUN_COL 1.*pow(vec3(1),vec3(1.4))//3.0*vec3(0.9, 0.8, 0.7)
#define SKY_COL 1+0*.02*vec3(1)//vec3(.2,.2,.6)//4.*vec3(.1,.41,.6)//(mix(vec3(.04,.10,.3),SUN_COL,pow(clamp(dot(cam_ray.dir,normalize(SUN_DIR)),0,1),5)))


#define MEDIUM_SCA 0.0*0.23*vec3(.04,.04,.09)//.13*vec3(.2,.4,.1) //scattering per channel
#define MEDIUM_ABS 0.0*1.3*vec3(.01,.01,.003)//.21*vec3(.3,.1,.051) //absorption per channel
#define FOG_AMT 0.*.521

#define AO_DIST 0.362
#define AO_STEPS 8
#define AO_POW .5
#define SHADOW_SHARPNESS 20//mix(70,70/scal,(time/(2*PI)))

#define COPIES 1
uniform vec4 dials;
#define COPY_POS dials.xyz //vec3(.547,.1654,.063)
uniform vec4 dials2;
#define COPY_ROT dials2.xyz //vec3(0.,.11325,0.)
uniform vec4 dials4;

#define PI 3.14159
in VertexData
{
    vec2 v_texcoord;
} inData;

struct Ray 
{
    vec3 ori;
    vec3 dir;
    float extent;
    vec3 norm;
    
};
struct MR 
{
    float dts;
    vec4 mat;
};
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

// All components are in the range [0…1], including hue.
vec3 hsv2rgb(vec3 c)
{
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}
vec3 cosPalette(float t, vec3 a,vec3 b,vec3 c,vec3 d){
    return a+b*cos(2*PI*(c*t+d));
}
void pR(inout vec2 p, float a) {
    p = cos(a)*p + sin(a)*vec2(p.y, -p.x);
}
void pR45(inout vec2 p) {
    p = (p + vec2(p.y, -p.x))*sqrt(0.5);
}
// Extracts the rotation axis from a rotation matrix.
// Returns a normalized axis vector (or vec3(0,0,1) for identity/zero-angle case).
// This is the eigenvector of R with eigenvalue 1.
vec3 rotationAxis(mat3 R) {
    // The axis is proportional to the skew-symmetric part: (R - R^T)
    // which gives us [R21-R12, R02-R20, R10-R01]
    vec3 axis = vec3(
        R[1][2] - R[2][1],
        R[2][0] - R[0][2],
        R[0][1] - R[1][0]
    );

    float len = length(axis);
    if (len < 1e-6) {
        // Rotation angle is 0 (or 180°). Fall back to a default.
        return vec3(0.0, 0.0, 1.0);
    }

    return axis / len;
}
// Builds a rotation matrix that interpolates from identity (theta=0)
// to the full rotation described by euler_angles (theta=1).
// Internally: extracts the axis and total angle from the Euler rotation,
// then rebuilds via axis-angle scaled by theta.
// Usage: mat3 R = axisAngleMatrix(vec3(pitch, yaw, roll), t);
//        vec3 rotated = R * p;  // left-multiply
mat3 axisAngleMatrix(vec3 euler, float theta) {
    // Build the full rotation to extract its axis and angle
    float cp = cos(euler.x), sp = sin(euler.x);
    float cy = cos(euler.y), sy = sin(euler.y);
    float cr = cos(euler.z), sr = sin(euler.z);
    // Full rotation matrix (Rz * Ry * Rx), column-major
    mat3 R = mat3(
        cy * cr,                   cy * sr,                  -sy,
       -cp * sr + sp * sy * cr,    cp * cr + sp * sy * sr,    sp * cy,
        sp * sr + cp * sy * cr,   -sp * cr + cp * sy * sr,    cp * cy
    );
    // Total angle from trace: cos(a) = (trace - 1) / 2
    float tr = R[0][0] + R[1][1] + R[2][2];
    float totalAngle = acos(clamp((tr - 1.0) * 0.5, -1.0, 1.0));
    // Near-zero rotation: just return identity
    if (totalAngle < 1e-6) return mat3(1.0);
    // Extract axis from skew-symmetric part
    vec3 axis = normalize(vec3(
        R[1][2] - R[2][1],
        R[2][0] - R[0][2],
        R[0][1] - R[1][0]
    ));

    // Rebuild at scaled angle
    float a = totalAngle * theta;
    float c = cos(a), s = sin(a), t = 1.0 - c;
    float x = axis.x, y = axis.y, z = axis.z;

    return mat3(
        x*x*t + c,    x*y*t + z*s,  x*z*t - y*s,
        x*y*t - z*s,  y*y*t + c,    y*z*t + x*s,
        x*z*t + y*s,  y*z*t - x*s,  z*z*t + c
    );
}
// integer hash copied from Hugo Elias
float hash(int n)
{
    n = (n << 13) ^ n;
    n = n * (n * n * 15731 + 789221) + 1376312589;
    return -1.0 + 2.0 * float(n & 0x0fffffff) / float(0x0fffffff);
}

// 2D gradient noise
float gnoise(in vec2 p)
{
    ivec2 i = ivec2(floor(p));
    vec2  f = fract(p);
    vec2  u = f * f * (3.0 - 2.0 * f);

    // hash each corner using a combined integer key
    float a = hash(i.x + i.y * 57);
    float b = hash(i.x + 1 + i.y * 57);
    float c = hash(i.x + (i.y + 1) * 57);
    float d = hash(i.x + 1 + (i.y + 1) * 57);

    return mix(mix(a, b, u.x),
               mix(c, d, u.x), u.y);
}

// 2D fbm
float fbm(in vec2 p, in float G)
{
    p += vec2(26.06, 17.43);
    float n = 0.0;
    float s = 1.0;
    float a = 0.0;
    float f = 1.0;
    for (int i = 0; i < 2; i++)
    {
        n += s * gnoise(p * f);
        a += s;
        s *= G;
        f *= 2.0;
        p += vec2(0.31, 0.73);
    }
    return n;
}

float pMod1(inout float p, float size) {
    float halfsize = size*0.5;
    float c = floor((p + halfsize)/size);
    p = mod(p + halfsize, size) - halfsize;
    return c;
}
// Repeat in two dimensions
vec2 pMod2(inout vec2 p, vec2 size) {
    vec2 c = floor((p + size*0.5)/size);
    p = mod(p + size*0.5,size) - size*0.5;
    return c;
}
// Repeat in three dimensions
vec3 pMod3(inout vec3 p, vec3 size) {
    vec3 c = floor((p + size*0.5)/size);
    p = mod(p + size*0.5, size) - size*0.5;
    return c;
}
// first object gets a capenter-style tongue attached
float fOpTongue(float a, float b, float ra, float rb) {
    return min(a, max(a - ra, abs(b) - rb));
}
// first object gets a capenter-style groove cut out
float fOpGroove(float a, float b, float ra, float rb) {
    return max(a, min(a + ra, rb - abs(b)));
}
// first object gets a v-shaped engraving where it intersect the second
float fOpEngrave(float a, float b, float r) {
    return max(a, (a + r - abs(b))*sqrt(0.5));
}

// Repeat only a few times: from indices <start> to <stop> (similar to above, but more flexible)
float pModInterval1(inout float p, float size, float start, float stop) {
    float halfsize = size*0.5;
    float c = floor((p + halfsize)/size);
    p = mod(p+halfsize, size) - halfsize;
    if (c > stop) { //yes, this might not be the best thing numerically.
        p += size*(c - stop);
        c = stop;
    }
    if (c <start) {
        p += size*(c - start);
        c = start;
    }
    return c;
}

// Repeat around the origin by a fixed angle.
// For easier use, num of repetitions is use to specify the angle.
float pModPolar(inout vec2 p, float repetitions) {
    float angle = 2*PI/repetitions;
    float a = atan(p.y, p.x) + angle/2.;
    float r = length(p);
    float c = floor(a/angle);
    a = mod(a,angle) - angle/2.;
    p = vec2(cos(a), sin(a))*r;
    // For an odd number of repetitions, fix cell index of the cell in -x direction
    // (cell index would be e.g. -5 and 5 in the two halves of the cell):
    if (abs(c) >= (repetitions/2)) c = abs(c);
    return c;
}
float sdBox( vec3 p, vec3 b )
{
  vec3 q = abs(p) - b;
  return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0);
}
float sdTorus( vec3 p, vec2 t )
{
  vec2 q = vec2(length(p.xz)-t.x,p.y);
  return length(q)-t.y;
}
float sdSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}
float sdRoundCone( vec3 p, vec3 a, vec3 b, float r1, float r2 )
{
  vec3  ba = b - a;
  float l2 = dot(ba,ba);
  float rr = r1 - r2;
  float a2 = l2 - rr*rr;
  float il2 = 1.0/l2;
    
  vec3 pa = p - a;
  float y = dot(pa,ba);
  float z = y - l2;
  float x2 = dot( pa*l2 - ba*y, pa*l2 - ba*y );
  float y2 = y*y*l2;
  float z2 = z*z*l2;

  // single square root!
  float k = sign(rr)*rr*rr*x2;
  if( sign(z)*a2*z2>k ) return  sqrt(x2 + z2)        *il2 - r2;
  if( sign(y)*a2*y2<k ) return  sqrt(x2 + y2)        *il2 - r1;
                        return (sqrt(x2*a2*il2)+y*rr)*il2 - r1;
}
float sdPyramid( vec3 p, float h )
{
  float m2 = h*h + 0.25;
    
  p.xz = abs(p.xz);
  p.xz = (p.z>p.x) ? p.zx : p.xz;
  p.xz -= 0.5;

  vec3 q = vec3( p.z, h*p.y - 0.5*p.x, h*p.x + 0.5*p.y);
  float s = max(-q.x,0.0);
  float t = clamp( (q.y-0.5*p.z)/(m2+0.25), 0.0, 1.0 );
  float a = m2*(q.x+s)*(q.x+s) + q.y*q.y;
  float b = m2*(q.x+0.5*t)*(q.x+0.5*t) + (q.y-m2*t)*(q.y-m2*t);
    
  float d2 = min(q.y,-q.x*m2-q.y*0.5) > 0.0 ? 0.0 : min(a,b);
  return sqrt( (d2+q.z*q.z)/m2 ) * sign(max(q.z,-p.y));
}


// quadratic polynomial
float smin( float a, float b, float k )
{
    k *= 4.0;
    float h = max( k-abs(a-b), 0.0 )/k;
    return min(a,b) - h*h*k*(1.0/4.0);
}
float smax( float a, float b, float k){
    return -smin(-a,-b,k);
}


MR smapMin(MR a, MR b, float k){
// quadratic polynomial
    float h = 1.0 - min( abs(a.dts-b.dts)/(4.0*k), 1.0 );
    float w = h*h;
    float m = w*0.5;
    float s = w*k;
    vec2 smin_result =  (a.dts<b.dts) ? vec2(a.dts-s,m) : vec2(b.dts-s,1.0-m);
    
    return MR( smin_result.x, mix(a.mat,b.mat,smin_result.y));
}
MR mapMin(MR a, MR b){
    return a.dts<b.dts?a:b;
}
float dot2(vec3 a){return dot(a,a);} 
float udTri( vec3 p, vec3 a, vec3 b, vec3 c )
{
  vec3 ba = b - a; vec3 pa = p - a;
  vec3 cb = c - b; vec3 pb = p - b;
  vec3 ac = a - c; vec3 pc = p - c;
  vec3 nor = cross( ba, ac );

  return sqrt(
    (sign(dot(cross(ba,nor),pa)) +
     sign(dot(cross(cb,nor),pb)) +
     sign(dot(cross(ac,nor),pc))<2.0)
     ?
     min( min(
     dot2(ba*clamp(dot(ba,pa)/dot2(ba),0.0,1.0)-pa),
     dot2(cb*clamp(dot(cb,pb)/dot2(cb),0.0,1.0)-pb) ),
     dot2(ac*clamp(dot(ac,pc)/dot2(ac),0.0,1.0)-pc) )
     :
     dot(nor,pa)*dot(nor,pa)/dot2(nor) );
}
float sdCone( vec3 p, vec2 c, float h )
{
  // c is the sin/cos of the angle, h is height
  // Alternatively pass q instead of (c,h),
  // which is the point at the base in 2D
  vec2 q = h*vec2(c.x/c.y,-1.0);
    
  vec2 w = vec2( length(p.xz), p.y );
  vec2 a = w - q*clamp( dot(w,q)/dot(q,q), 0.0, 1.0 );
  vec2 b = w - q*vec2( clamp( w.x/q.x, 0.0, 1.0 ), 1.0 );
  float k = sign( q.y );
  float d = min(dot( a, a ),dot(b, b));
  float s = max( k*(w.x*q.y-w.y*q.x),k*(w.y-q.y)  );
  return sqrt(d)*sign(s);
}
float sdCyl( vec3 p, float r, float h )
{
  vec2 d = abs(vec2(length(p.xz),p.y)) - vec2(r,h);
  return min(max(d.x,d.y),0.0) + length(max(d,0.0));
}
float sdBlob( vec3 p, vec3 r )
{
  float k0 = length(p/r);
  float k1 = length(p/(r*r));
  return k0*(k0-1.0)/k1;
}
float sdVesicaSegment( in vec3 p, in vec3 a, in vec3 b, in float w )
{
    vec3  c = (a+b)*0.5;
    float l = length(b-a);
    vec3  v = (b-a)/l;
    float y = dot(p-c,v);
    vec2  q = vec2(length(p-c-y*v),abs(y));
    
    float r = 0.5*l;
    float d = 0.5*(r*r-w*w)/w;
    vec3  h = (r*q.x<d*(q.y-r)) ? vec3(0.0,r,0.0) : vec3(-d,0.0,d+w);
 
    return length(q-h.xy) - h.z;
}
//PHYSICS EMISSION HERE


#define alpha -1.
#define angles COPY_ROT.xyz*PI
float t_schedule(float x){
x/=PI*2;
x=fract(x);
return x;
}
float t = t_schedule(time);
mat3 baseRot = axisAngleMatrix(angles*PI,alpha*t);
mat3 fullRot = axisAngleMatrix(angles*PI,alpha);
mat3 worldRot = axisAngleMatrix(angles*PI,alpha*time/2/PI);
float scal = 1./1.5;
vec3 axis = rotationAxis(fullRot);
uniform vec4 dials3;

vec4 logp(vec3 p){
    #define SCALE (6./PI) 
    vec2 p2 = p.xz;
    float r = length(p2);
    float theta = atan(p2.y,p2.x);
    p2 = vec2(log(r),theta);
    p2*=SCALE;//scale for -PI,PI interval
    float mul = r/SCALE;
    return vec4(p2.x,p.y/mul,p2.y,mul);
}
vec3 C;
vec3 funCen;
float Q = 3.0, R = 3.0; // P = 2, require 1/Q+1/R > 1/2
int NFOLDS = 2; // 5 enough for icosahedron, but might need more for prisms
// Setup folding planes
vec3 init(float Q, float R) {
  float q = PI/Q;
  float r = PI/R;
  float x = -cos(r);
  float y = -cos(q);
  float z = sqrt(1.0-x*x-y*y);
  return vec3(x,y,z);
}

vec3 wythoff(vec3 p, vec3 C, int NFOLDS) {
  for (int i = 0; i < NFOLDS; i++) {
    p.xy = abs(p.xy);
    float k = dot(p,C);
    if (k >= 0.0) break;
    p -= 2.0*k*C;
  }
  return p;
}
vec3 fundamentalCenter(float Q, float R) {
    vec3 n1 = vec3(1, 0, 0);
    vec3 n2 = vec3(0, 1, 0);
    vec3 C = init(Q, R);

    vec3 v1 = normalize(cross(n1, n2)); // = (0, 0, 1)
    vec3 v2 = normalize(cross(n2, C));
    vec3 v3 = normalize(cross(C, n1));

    return normalize(v1 + v2 + v3);
}
MR moon(vec3 p){
    p/=400;
    MR result = MR( 999,vec4(.2));
        float scal = .09;//dials3.x;
    float offs = dials3.w*5;
    float running = 1;
    p=wythoff(p,C,NFOLDS);
    result.dts = min(result.dts,length(p)-1);
    p-=funCen*1;
    result.dts = max(result.dts, -(length(p)-scal));
    p=wythoff(p,C,NFOLDS);
    p-=funCen*scal;
    result.dts = 400*max(result.dts,-(length(p)-scal*scal));
    return result;
}
    #define shoulder vec3(.8,.85,-.00)
    #define elbow vec3(1.2,-.30,-.1)
    #define wrist vec3(1.29,-1.7,-.2)
    #define hip vec3(.45,-1.25,0)
    #define knee vec3(.7,-3.5,-.5)
    #define ankle vec3(.7,-5.,-.25)
    #define toe (ankle+vec3(0,-.31,-.4))
MR scene(vec3 p,float phase){
    
    //return sdFish(p,phase);
    //if(phase<-1.7){return MR(99999,vec4(0));}//kill the small ones
    p.xyz+=COPY_POS*15;//vec3(-.6144,.0024,.0554)*vec3(10,10,1)+vec3(0,0,1.2);//+vec3(0,0,3*min(1.5,time));
    vec3 physp;
    mat3 physr;
    astroA(phase,physp,physr);
    p+=physp;
    p = physr*p;
    pR(p.xz,dials3.z);
    vec3 op = p;
    #define suit_mat vec4(.02,.01,.01,.12)
    MR result = MR(99990,vec4(.02,.01,.01,0.12));
    float body = sdBlob(p,vec3(1,2,1));
    if(body>4){result.dts = body-3; return result;}
    p-=vec3(0,0,1.2);
    float pack = sdBox(p,vec3(1.2,2.4,.7)-.2)-.2;
    
    p=op;

    p.x=abs(p.x);
    float leg = sdRoundCone(p,hip,knee,.55,.55);
    leg = smin(leg,sdRoundCone(p,knee,ankle,.6,.4),.01);
    p-=toe;
    pR(p.yz,-.4);
    leg = smin(leg,sdBlob(p,vec3(.4,.3,.65)),.051);
    body = smin(body,leg,.1);
    p=op;
        p.x=abs(p.x);//bilateral symmetry
    p-=shoulder;
    pR(p.yz,.5*3.14*(op.x>0?1:0));
    pR(p.xy,dials3.y*3.14*(op.x>0?1:0));
    p+=shoulder;
    float arm = sdRoundCone(p,shoulder,elbow,.65,.45);
    arm = smin(arm,sdRoundCone(p,elbow,wrist,.45,.35),.02);
    body = min(body,arm);
    p=op;
    p-=vec3(0,2,-0.31);
    float head = length(p)-.81;
    vec4 head_mat = vec4(.002,.002,.001,.39);
    result.dts = body;
    result.dts = smin(result.dts,pack,.2);
    result = smapMin(result,MR(head,head_mat),.051);
    
    //result = mapMin(result,MR(op.y+5,vec4(.2)));
    return result;
}
MR scenebb(vec3 p,float phase, float index){
    p+=COPY_POS*15;
    return MR(length(p)-6,vec4(index));
}
MR map(vec3 p){
    //log slide
    //pR(p.xy,PI/2);
    vec3 op = p;
    p/=pow(scal,t);
    p = baseRot*p;//pR(p.xz,alpha*t);
    MR result = MR(999, vec4(0));
    
    vec3 mp = p;
            vec3 physp;
            mat3 physr;
            astroA(alpha*t,physp,physr);
            mp-=physp;
            mp = mp*physr;
    result = scenebb(mp,alpha*t,0);
    mp = p;
    #ifdef COPIES
    for(int i = 0;i<4;i++){
        mp/=scal;
        mp = fullRot*mp;//pR(mp.xz,alpha);
        float phase = alpha*(t+i+1);
            vec3 physp;
            mat3 physr;
            astroA(phase,physp,physr);
            mp-=physp;
            mp = mp*physr;
        MR small = scenebb(mp,phase,i+1);
        small.dts*=pow(scal,i+1);
        result=mapMin(result,small);//,.1*pow(scal,i));
    }
    mp=p;
    for(int i = 0;i<4;i++){
        mp*=scal;
        mp = transpose(fullRot)*mp;//pR(mp.xz,-alpha);
        float phase = alpha*(t-i-1);
            vec3 physp;
            mat3 physr;
            astroA(phase,physp,physr);
            mp-=physp;
            mp = mp*physr;
        MR big = scenebb(mp,phase,-1-i);
        big.dts/=pow(scal,i+1);
        result = mapMin(result,big);//,.021/pow(scal,i+1));
    }
    #endif
    if(result.dts>3.){result.dts=pow(scal,t)*(result.dts-1.);return result;}//bounding box
    
    float ascal = pow(scal,-result.mat.x);
    mat3 arot = mat3(1,0,0,0,1,0,0,0,1);
    //if(abs(result.mat.x)>0){arot = fullRot;}
    for(int i = 0;i<abs(result.mat.x);i++){
        arot = arot * fullRot;
    }
    arot = result.mat.x<0 ? transpose(arot):arot;
    mp=p;
    mp*=ascal;
    mp = arot * mp;
            astroA(alpha*t,physp,physr);
            mp-=physp;
            mp = mp*physr;
    MR astro = scene(mp,alpha*t);
    astro.dts/=ascal;
    result = astro;
    
    result.dts*=pow(scal,t);
    return result;
    
    #ifdef COPIESNO
     mp = p;
    
    for(int i = ZERO;i<1;i++){
        mp/=scal;
        mp = fullRot*mp;//pR(mp.xz,alpha);
        MR small = scene(mp,alpha*(t+i+1));
        small.dts*=pow(scal,i+1);
        result=mapMin(result,small);//,.1*pow(scal,i));
    }
    
    mp=p;
    for(int i = ZERO;i<1;i++){
        mp*=scal;
        mp = transpose(fullRot)*mp;//pR(mp.xz,-alpha);
        MR big = scene(mp,alpha*(t-i-1));
        big.dts/=pow(scal,i+1);
        result = mapMin(result,big);//,.021/pow(scal,i+1));
    }
    
    #endif
    
    result.dts *=pow(scal,t);
    op = worldRot*op;
    //op = baseRot*op;
    result = mapMin(result,moon(op-axis*700));//+vec3(-0,35,550)));

return result;
}

vec3 calcNorm( in vec3 p, float extent ) // for function f(p)
{
    float h = NORM_DIST*extent;      // replace by an appropriate value
    vec3 n = vec3(0.0);
    for( int i=ZERO; i<4; i++ )
    {
        vec3 e = 0.5773*(2.0*vec3((((i+3)>>1)&1),((i>>1)&1),(i&1))-1.0);
        n += e*map(p+e*h).dts;
    }
    return normalize(n);
}

MR march(inout Ray r){
    MR result = MR(MAX_DISTANCE,vec4(-1));
    for(int i = ZERO; i< MAX_STEPS && r.extent<MAX_DISTANCE; i++){
        vec3 pos = r.ori + r.dir * r.extent;
        result = map(pos);
        float dts = result.dts;
        vec4 mat = result.mat;
        if(dts < HIT_DISTANCE){
            r.norm = calcNorm(pos,r.extent);
            return result;
        }
        r.extent += result.dts;
    }
    r.extent = min(r.extent,MAX_DISTANCE);//prevent sky banding with fog
    return result;
}
float calcAO(Ray r) {
    float aoDist = AO_DIST;
    float occ = 0.0;
    float itC = 0.0;
    vec3 pos = r.ori + r.dir * r.extent;
    for (int i = ZERO+1; i < AO_STEPS; i++) {
        itC++;
        float term = itC * aoDist - map(pos + r.norm * aoDist * itC).dts;
        occ += 1.0 / pow(2.0, itC) * term;
    }
    return 1.0 - clamp(AO_POW * occ / aoDist, 0.0, 1.0);
}
float occlude_march(Ray r, vec3 light_dir,float max_extent){
    Ray shadow_ray = Ray(r.ori + r.dir * r.extent, light_dir, 0.0, vec3(0));
    //#pragma optionNV(unroll none)
    for (int i = 0;i < 6;i++)
    {
        shadow_ray.ori += r.norm * SMALL_BUMP*pow(2,float(i+1));
        if (map(shadow_ray.ori).dts > HIT_DISTANCE*2)break;
    }
    //MR shadow_hit = march(shadow_ray);
    
    MR shadow_hit = MR(MAX_DISTANCE,vec4(-1));
    float closest_approach = MAX_DISTANCE;
    for(int i = ZERO; i< MAX_SHADOW_STEPS && shadow_ray.extent<max_extent; i++){
        shadow_hit = map(shadow_ray.ori + shadow_ray.dir * shadow_ray.extent);
        float dts = shadow_hit.dts;
        
        vec4 mat = shadow_hit.mat;
        if(dts < HIT_DISTANCE){
            closest_approach = 0;
            break;
        }
        closest_approach = min(closest_approach,SHADOW_SHARPNESS*dts/shadow_ray.extent);
        shadow_ray.extent += shadow_hit.dts;
    }
    return clamp(closest_approach,0,1);
}

Ray cam_ray;
Ray getCam(vec2 uv){
    uv.y*=resolution.y/resolution.x;
    vec3 dir = normalize(vec3(uv,FOCAL_LENGTH));
    
    vec3 forward = normalize(CAMTAR - CAMPOS);
    vec3 up = vec3(0,1,0);
    vec3 right = normalize(cross(forward,up));
    up = normalize(cross(right,forward));
    dir= mat3(right,up,forward)*dir;
    return Ray (CAMPOS,dir,0,vec3(0));
}

vec3 sun_lighting(Ray r,vec3 albedo,vec3 light_col, float smoothness){
    float geom = clamp(dot(SUN_DIR,r.norm),0,1);
    float max_ext = MAX_DISTANCE;
    if(length(r.extent)>250){max_ext = 150;}//KEEP THE MOON FROM BEING SHADOWED BY ASTRONAUTS
    float shadow = occlude_march(r,SUN_DIR,max_ext);
    vec3 result = albedo*geom*light_col*shadow;//diffuse
    {//specular
        vec3 hv = normalize(-r.dir+SUN_DIR);
        float fresnel = clamp(dot(r.dir,SUN_DIR),0,1);
        fresnel = .2 + .8*pow(fresnel,5);
        float spec = clamp(dot(hv,r.norm),0,1);
        spec = pow(spec, exp(10.*smoothness));
        result += .93*spec * fresnel * shadow * geom * light_col;
    }
    return result;
}


vec3 ambient_lighting(Ray r,vec3 albedo,vec3 ambient_col){
    float lenp = length(r.ori+r.dir*r.extent);
    return calcAO(r)*albedo*ambient_col;
}
vec3 lighting(MR hit, Ray r,vec3 light_col, vec3 ambient_col){
    vec3 albedo = hit.mat.xyz;
    vec3 result = sun_lighting(r,albedo,light_col,hit.mat.w);//point_lighting(r,albedo*10.,vec3(-.20,1.9,-0.9)-COPY_POS*15.+15.*vec3(.608,.174,.063),normalize(vec3(1,-.3,0)));
    result += ambient_lighting(r,albedo,ambient_col);
    return result;
}
vec3 get_sky(vec3 dir){
vec3 sun_spot = SUN_COL*pow(clamp(dot(SUN_DIR,dir),0,1),80);
dir = worldRot*dir;

pMod2(dir.yz,vec2(.03));
pR(dir.yz,1.3);
pMod2(dir.xz,vec2(.03));
pR(dir.xz,1.15);
pMod2(dir.xy,vec2(.03));

return sun_spot+0.*SKY_COL+clamp(1-length(dir.xy)*700,0,.1);
}
uniform sampler2D texture4;
out vec4 fragColor;
void main(void)
{
    C = init(Q,R); 
    funCen = fundamentalCenter(Q,R);
    axis *= -sign(axis.y);
    vec2 uv = -1.0 + 2.0 * inData.v_texcoord.xy;
    cam_ray = getCam(uv);
    MR hit = march(cam_ray);
    vec3 col;
    float depth = 0;//.32*clamp(-.23*((cam_ray.ori+cam_ray.dir*cam_ray.extent).y-100),0,80);
    vec3 depth_tint = exp(-depth * (MEDIUM_SCA+MEDIUM_ABS));
    vec3 light_col = SUN_COL * depth_tint;
    if(hit.dts<1){
        vec3 light = lighting(hit,cam_ray,light_col,SKY_COL*depth_tint);
        col = light;
    }
    else{
    
    col = get_sky(cam_ray.dir);
    }

    //fog
    //col = mix(FOG_COL,col,exp(-cam_ray.extent*FOG_AMT));

    vec3 extinction = exp(-cam_ray.extent*FOG_AMT*(MEDIUM_SCA+MEDIUM_ABS));
    vec3 inscattering = 1.-exp(-cam_ray.extent*FOG_AMT*MEDIUM_SCA);
    
    vec3 scatter_col =  MEDIUM_SCA/(MEDIUM_SCA+MEDIUM_ABS) * light_col;
    col = col * extinction + scatter_col*inscattering;
    col = pow(1.*col, vec3(1.0 / 2.2));
    fragColor = vec4(vec3((col)), 1.0);
    uv = inData.v_texcoord.xy;
    uv.xy=1-uv.xy;
    uv.y*=929./615.;
    uv.xy+=vec2(-.15,-.29);
    uv*=1.5;
    //fragColor = mix(fragColor,texture(texture4,uv),.21);
}