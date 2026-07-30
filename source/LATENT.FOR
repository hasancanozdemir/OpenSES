      SUBROUTINE LATENT(TD,TW,W)                                        
C                                                                       
C     THIS SUBROUTINE CONVERTS DRY AND WET BULB TEMPERATURES            
C     INTO SPECIFIC HUMIDITY IN LB/LB                                   
C                                                                       
C     TD IS THE DRY BULB TEMPERATURE IN DEG. F.                         
C     TW IS THE WET BULB TWMPERATURE IN DEG. F.                         
C     W IS THE SPECIFIC HUMIDITY IN LBS OF WATER PER LB OF AIR          
C                                                                       
C                                                                       
C     INCLUDE                                  ( DATE: 15 AUGUST 1997 ) 
C     
      INCLUDE  'DSHARE'                                                 
C                                                                       
                                                                        
C                                                                       
                                                                        
      DATA  A,B,C,D,PC,TC/3.2437814,5.86826E-03,1.1702379E-08,          
     1     2.1878462E-03,218.167,647.27 /                               
C***   MAP SI INPUTS TO LEGACY FORMULATION UNITS (DEG F, IN HG).
      IF (INPUT_UNITS .EQ. UNIT_SI) THEN
      TD_F = TD*9.0/5.0 + 32.0
      TW_F = TW*9.0/5.0 + 32.0
      PAMB_INHG = PAMB*0.2952998751
      ELSE
      TD_F = TD
      TW_F = TW
      PAMB_INHG = PAMB
      END IF
C***   CHANGE DEG F TO DEG K                                            
      T = 5.0 * (TW_F - 32.0)/ 9.0 + 273.16                             
      X = TC - T                                                        
      ALPHA = X * (A+B*X + C* X**3) / ( T*(1.0 + D*X ) )                
      ALPHA = -2.3025851 * ALPHA                                        
      PW = PC * EXP( ALPHA)                                             
C*****  CONVERT P TO INCHES HG                                          
      PW=PW*SAINHG                                                      
      PS = PW - (PAMB_INHG-PW)*(TD_F-TW_F)/(2800. - 1.3*TW_F)          
      W = 0.622 * PS / (PAMB_INHG - PS)                                
      RETURN                                                            
      END                                                               
